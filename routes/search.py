"""
Topic Search routes — search freelance platforms for demand data.

Data priority for platform results:
  1. Fresh row in topic_intelligence (from nightly demand_refresh / prior live scrape)
  2. Live Playwright scrape of Upwork / Fiverr / Contra (cached back to topic_intelligence)
  3. Heuristic fallback only when scrapers + cache both fail (flagged as synthetic)
"""
import asyncio
import logging
import re
from flask import Blueprint, render_template, request, jsonify, g, url_for
from services.supabase_client import get_supabase
from routes.topics import CURATED_TOPICS
from services.topic_data import (
    fetch_topic_intelligence,
    platform_results_from_intel,
    platform_results_from_scrape,
    cache_scrape_to_intelligence,
    get_enriched_topics,
    is_stale,
)

search_bp = Blueprint("search", __name__, url_prefix="/search")
logger = logging.getLogger(__name__)

# Cap live scrape time so the search endpoint stays responsive
SCRAPE_TIMEOUT_SEC = 25


def _slugify(query: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    return s[:80] or "topic"


@search_bp.route("/api", methods=["GET"])
def search_api():
    """Search for a topic across freelance platforms.
    Returns demand data if found, or suggests alternatives."""
    query = request.args.get("q", "").strip().lower()
    if not query or len(query) < 2:
        return jsonify({"error": "Query too short", "results": []})

    # Curated matches with live demand overlay
    sb = None
    try:
        sb = get_supabase()
    except Exception:
        sb = None

    curated_base = [t for t in CURATED_TOPICS if query in t["name"].lower() or query in t["slug"]]
    try:
        curated_matches = get_enriched_topics(sb, curated_base) if curated_base else []
    except Exception:
        curated_matches = curated_base

    platform_results = _get_platform_demand_data(query, sb=sb, curated_matches=curated_matches)

    response = {
        "query": query,
        "curated_matches": curated_matches[:3],
        "platform_results": platform_results,
        "curated_count": len(curated_matches),
    }

    # Check if user has platforms linked (W1 scenario still surfaces the notice,
    # but we no longer block live data behind it — demand is public market data).
    if g.user and sb is not None:
        try:
            plat_resp = sb.table("user_platforms").select("id").eq("user_id", g.user["id"]).limit(1).execute()
            response["platforms_linked"] = len(plat_resp.data or []) > 0
        except Exception:
            response["platforms_linked"] = False
    else:
        response["platforms_linked"] = False

    return jsonify(response)


@search_bp.route("/suggestions")
def suggestions():
    """Return popular topic suggestions with live job counts when available."""
    sb = None
    try:
        sb = get_supabase()
    except Exception:
        sb = None

    try:
        live = get_enriched_topics(sb, CURATED_TOPICS) if sb is not None else CURATED_TOPICS
    except Exception:
        live = CURATED_TOPICS

    suggestions_list = [
        {"name": t["name"], "slug": t["slug"], "jobs": t.get("job_count", 0), "rate": t.get("avg_rate", 0)}
        for t in live
    ]
    # Common freelance topics (static extras — live-scraped on full search)
    extras = [
        {"name": "Machine Learning", "slug": "machine-learning", "jobs": 156, "rate": 55},
        {"name": "React Development", "slug": "react-development", "jobs": 890, "rate": 45},
        {"name": "Mobile App Development", "slug": "mobile-app-development", "jobs": 1200, "rate": 50},
        {"name": "Graphic Design", "slug": "graphic-design", "jobs": 3400, "rate": 25},
        {"name": "Video Editing", "slug": "video-editing", "jobs": 2100, "rate": 30},
        {"name": "Virtual Assistant", "slug": "virtual-assistant", "jobs": 4500, "rate": 15},
        {"name": "Copywriting", "slug": "copywriting", "jobs": 2800, "rate": 35},
        {"name": "Social Media Management", "slug": "social-media-management", "jobs": 1900, "rate": 28},
    ]
    # Overlay extras with any cached intelligence
    if sb is not None:
        try:
            intel = fetch_topic_intelligence(sb, [e["slug"] for e in extras])
            for e in extras:
                row = intel.get(e["slug"])
                if row and row.get("freelance_job_count"):
                    e["jobs"] = int(row["freelance_job_count"])
                    if row.get("avg_rate"):
                        e["rate"] = int(round(float(row["avg_rate"])))
        except Exception:
            pass
    suggestions_list.extend(extras)
    return jsonify(suggestions_list)


def _get_platform_demand_data(query: str, sb=None, curated_matches=None) -> dict:
    """Resolve freelance demand for a query.

    Tries (in order): fresh topic_intelligence cache → live Playwright scrape
    → heuristic synthetic numbers (explicitly flagged).
    """
    slug = _slugify(query)

    # 1) Cache hit from topic_intelligence (prefer curated slug if matched)
    candidate_slugs = []
    if curated_matches:
        candidate_slugs.extend(t["slug"] for t in curated_matches[:3])
    candidate_slugs.append(slug)

    stale_row = None
    if sb is not None:
        try:
            intel_map = fetch_topic_intelligence(sb, candidate_slugs)
            for s in candidate_slugs:
                row = intel_map.get(s)
                if not row:
                    continue
                # Use cache if it has real numbers and isn't ancient
                if (row.get("freelance_job_count") or 0) > 0 and not is_stale(row.get("last_updated"), hours=72):
                    logger.info(f"search '{query}': serving cached intelligence for {s}")
                    return platform_results_from_intel(row, query)
                # Stale-but-present: keep as fallback after scrape attempt
                if (row.get("freelance_job_count") or 0) > 0 and stale_row is None:
                    stale_row = row
        except Exception as e:
            logger.warning(f"intel cache lookup failed: {e}")
            stale_row = None

    # 2) Live scrape (Upwork + Fiverr + Contra)
    scrape = _try_live_scrape(query)
    if scrape is not None:
        ui = platform_results_from_scrape(scrape, query)
        total = sum(ui[p]["jobs"] for p in ("upwork", "fiverr", "contra"))
        if total > 0:
            # Cache under both the query-slug and any curated match slug
            if sb is not None:
                for s in dict.fromkeys(candidate_slugs):  # dedupe, preserve order
                    try:
                        cache_scrape_to_intelligence(sb, s, scrape, ui)
                    except Exception as e:
                        logger.warning(f"cache write failed for {s}: {e}")
            logger.info(f"search '{query}': live scrape returned {total} jobs")
            return ui
        logger.warning(f"search '{query}': live scrape returned 0 jobs across platforms")

    # 3) Stale cache is still better than inventing numbers
    if sb is not None and stale_row is None:
        # re-fetch without freshness filter
        try:
            intel_map = fetch_topic_intelligence(sb, candidate_slugs)
            for s in candidate_slugs:
                if intel_map.get(s) and (intel_map[s].get("freelance_job_count") or 0) > 0:
                    stale_row = intel_map[s]
                    break
        except Exception:
            pass
    if stale_row is not None:
        ui = platform_results_from_intel(stale_row, query)
        ui["stale"] = True
        ui["data_source"] = "stale-cache"
        return ui

    # 4) Last resort: heuristic (clearly marked synthetic so UI can warn)
    return _heuristic_platform_data(query)


def _try_live_scrape(query: str):
    """Run Playwright scrapers; return dict or None on total failure."""
    try:
        from services.platform_scraper import scrape_all_platforms

        async def _run():
            return await asyncio.wait_for(scrape_all_platforms(query), timeout=SCRAPE_TIMEOUT_SEC)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Nested loop (e.g. under gunicorn + gevent) — spin a new one in a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(lambda: asyncio.run(_run())).result(timeout=SCRAPE_TIMEOUT_SEC + 5)
            return loop.run_until_complete(_run())
        except RuntimeError:
            return asyncio.run(_run())
    except Exception as e:
        logger.warning(f"live scrape failed for '{query}': {e}")
        return None


def _heuristic_platform_data(query: str) -> dict:
    """Synthetic demand numbers — only used when live data is unavailable.
    Flagged so the UI can show a 'estimated' badge instead of claiming live data.
    """
    high_demand_keywords = ["web", "python", "data", "content", "writing", "seo",
                           "wordpress", "shopify", "react", "mobile", "design",
                           "marketing", "social media", "video", "excel"]
    medium_demand = ["machine learning", "ai", "blockchain", "docker", "kubernetes",
                    "aws", "azure", "devops", "testing", "qa"]

    score = 0
    for kw in high_demand_keywords:
        if kw in query:
            score += 20
    for kw in medium_demand:
        if kw in query:
            score += 10

    score = max(10, min(95, score + len(query) * 2))
    job_count = int(score * 15 + len(query) * 3)
    avg_rate = 15 + int(score * 0.4)

    return {
        "upwork": {
            "status": "available",
            "jobs": job_count,
            "avg_rate": avg_rate,
            "url": f"https://www.upwork.com/nx/search/jobs/?q={query}",
            "source": "synthetic",
        },
        "fiverr": {
            "status": "available",
            "jobs": int(job_count * 1.5),
            "avg_rate": max(10, avg_rate - 5),
            "url": f"https://www.fiverr.com/search/gigs?query={query}",
            "source": "synthetic",
        },
        "contra": {
            "status": "available",
            "jobs": int(job_count * 0.3),
            "avg_rate": avg_rate + 5,
            "url": f"https://contra.com/search?q={query}",
            "source": "synthetic",
        },
        "demand_score": score,
        "trend": "growing" if score > 50 else "stable",
        "estimated_time_to_gig": f"{max(1, 5 - score // 20)} weeks",
        "difficulty": "Beginner" if score < 30 else "Intermediate" if score < 60 else "Advanced",
        "data_source": "synthetic",
        "stale": True,
        "last_updated": None,
    }


@search_bp.route("/curriculum/<slug>")
def get_curriculum(slug):
    """API: fetch curriculum days for a topic."""
    from services.supabase_client import get_supabase
    try:
        sb = get_supabase()
        t = sb.table("topics").select("id").eq("slug", slug).limit(1).execute()
        if not t.data:
            return jsonify({"days": []})
        c = sb.table("curricula").select("id").eq("topic_id", t.data[0]["id"]).limit(1).execute()
        if not c.data:
            return jsonify({"days": []})
        d = sb.table("curriculum_days").select("*").eq("curriculum_id", c.data[0]["id"]).order("day_number").limit(30).execute()
        return jsonify({"days": d.data or [], "count": len(d.data or [])})
    except Exception as e:
        return jsonify({"error": str(e), "days": []})
