"""
Topic demand data — single source of truth for job counts / rates / scores.

Priority:
  1. Live rows in `topic_intelligence` (filled by demand_refresh + live scrapes)
  2. Hardcoded CURATED_TOPICS defaults (fallback when DB is empty / offline)

Also exposes helpers to shape platform-breakdown dicts for the search UI.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# How long cached intelligence is considered "fresh" before we flag it stale
FRESHNESS_HOURS = 48


def _parse_ts(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        # Supabase returns ISO strings, sometimes with trailing Z
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def is_stale(last_updated, hours: int = FRESHNESS_HOURS) -> bool:
    ts = _parse_ts(last_updated)
    if not ts:
        return True
    age = datetime.now(timezone.utc) - ts
    return age.total_seconds() > hours * 3600


def fetch_topic_intelligence(sb, slugs: Optional[list[str]] = None) -> dict[str, dict]:
    """Load topic_intelligence rows keyed by topic slug.

    Returns {} on any failure so callers can fall back to hardcoded data.
    """
    try:
        q = sb.table("topic_intelligence").select(
            "topic,freelance_job_count,avg_rate,demand_trend,viability_score,"
            "last_updated,platform_breakdown"
        )
        if slugs:
            q = q.in_("topic", slugs)
        resp = q.execute()
        return {row["topic"]: row for row in (resp.data or []) if row.get("topic")}
    except Exception as e:
        # platform_breakdown column may not exist yet — retry without it
        msg = str(e)
        if "platform_breakdown" in msg or "PGRST" in msg:
            try:
                q = sb.table("topic_intelligence").select(
                    "topic,freelance_job_count,avg_rate,demand_trend,"
                    "viability_score,last_updated"
                )
                if slugs:
                    q = q.in_("topic", slugs)
                resp = q.execute()
                return {row["topic"]: row for row in (resp.data or []) if row.get("topic")}
            except Exception as e2:
                logger.warning(f"topic_intelligence fetch failed: {e2}")
                return {}
        logger.warning(f"topic_intelligence fetch failed: {e}")
        return {}


def merge_topic(base: dict, intel: Optional[dict]) -> dict:
    """Overlay live intelligence onto a curated topic dict (non-destructive copy)."""
    out = dict(base)
    if not intel:
        out["data_source"] = "curated"
        out["data_stale"] = True
        out["last_updated"] = None
        return out

    if intel.get("freelance_job_count") is not None:
        out["job_count"] = int(intel["freelance_job_count"] or 0)
    if intel.get("avg_rate") is not None:
        try:
            out["avg_rate"] = int(round(float(intel["avg_rate"])))
        except (TypeError, ValueError):
            pass
    if intel.get("viability_score") is not None:
        try:
            out["demand_score"] = int(round(float(intel["viability_score"])))
        except (TypeError, ValueError):
            pass
    if intel.get("demand_trend"):
        out["trend"] = intel["demand_trend"]

    last_updated = intel.get("last_updated")
    out["last_updated"] = last_updated
    out["data_stale"] = is_stale(last_updated)
    out["data_source"] = "live"
    out["platform_breakdown"] = intel.get("platform_breakdown") or {}
    return out


def get_enriched_topics(sb, curated: list[dict]) -> list[dict]:
    """Return curated topics with live demand numbers overlaid when available."""
    slugs = [t["slug"] for t in curated]
    intel_map = fetch_topic_intelligence(sb, slugs) if sb is not None else {}
    return [merge_topic(t, intel_map.get(t["slug"])) for t in curated]


def get_enriched_topic(sb, curated_topic: dict) -> dict:
    intel_map = fetch_topic_intelligence(sb, [curated_topic["slug"]]) if sb is not None else {}
    return merge_topic(curated_topic, intel_map.get(curated_topic["slug"]))


def platform_results_from_intel(intel: dict, query: str) -> dict:
    """Shape a topic_intelligence row into the search UI's platform_results format."""
    breakdown = intel.get("platform_breakdown") or {}
    total_jobs = int(intel.get("freelance_job_count") or 0)
    avg_rate = float(intel.get("avg_rate") or 0)
    score = int(round(float(intel.get("viability_score") or 50)))
    trend = intel.get("demand_trend") or "stable"

    def _plat(name: str, jobs_fallback: int, rate_fallback: float, url: str) -> dict:
        raw = breakdown.get(name) if isinstance(breakdown, dict) else None
        if raw and isinstance(raw, dict) and (raw.get("job_count") or 0) > 0:
            return {
                "status": "available",
                "jobs": int(raw.get("job_count") or 0),
                "avg_rate": int(round(float(raw.get("avg_rate") or rate_fallback or 0))),
                "url": url,
                "source": "live",
            }
        # No per-platform breakdown — surface aggregate as Unavailable so UI
        # doesn't invent numbers, but keep total score visible.
        return {
            "status": "available" if jobs_fallback > 0 else "unreachable",
            "jobs": jobs_fallback,
            "avg_rate": int(round(rate_fallback or 0)),
            "url": url,
            "source": "aggregate" if jobs_fallback > 0 else "none",
        }

    # When we only have aggregates, distribute proportionally so cards aren't empty
    has_breakdown = any(
        isinstance(breakdown.get(p), dict) and (breakdown[p].get("job_count") or 0) > 0
        for p in ("upwork", "fiverr", "contra")
    )
    if has_breakdown:
        upwork = _plat("upwork", 0, avg_rate, f"https://www.upwork.com/nx/search/jobs/?q={query}")
        fiverr = _plat("fiverr", 0, max(10, avg_rate - 5), f"https://www.fiverr.com/search/gigs?query={query}")
        contra = _plat("contra", 0, avg_rate + 5, f"https://contra.com/search?q={query}")
    else:
        # Aggregate-only: put the total on upwork (highest weight) and zero others
        # so we don't fabricate Fiverr/Contra counts.
        upwork = {
            "status": "available" if total_jobs else "unreachable",
            "jobs": total_jobs,
            "avg_rate": int(round(avg_rate)),
            "url": f"https://www.upwork.com/nx/search/jobs/?q={query}",
            "source": "aggregate",
        }
        fiverr = {
            "status": "unreachable",
            "jobs": 0,
            "avg_rate": 0,
            "url": f"https://www.fiverr.com/search/gigs?query={query}",
            "source": "none",
        }
        contra = {
            "status": "unreachable",
            "jobs": 0,
            "avg_rate": 0,
            "url": f"https://contra.com/search?q={query}",
            "source": "none",
        }

    return {
        "upwork": upwork,
        "fiverr": fiverr,
        "contra": contra,
        "demand_score": score,
        "trend": trend,
        "estimated_time_to_gig": f"{max(1, 5 - score // 20)} weeks",
        "difficulty": "Beginner" if score < 30 else "Intermediate" if score < 60 else "Advanced",
        "data_source": "live",
        "last_updated": intel.get("last_updated"),
        "stale": is_stale(intel.get("last_updated")),
    }


def platform_results_from_scrape(results: dict, query: str) -> dict:
    """Shape raw PlatformDemandData (or None) scrape results into UI format."""
    def _one(name: str, data, url: str) -> dict:
        if data is None or isinstance(data, Exception):
            return {"status": "unreachable", "jobs": 0, "avg_rate": 0, "url": url, "source": "none"}
        return {
            "status": "available" if (data.job_count or 0) > 0 else "unreachable",
            "jobs": int(data.job_count or 0),
            "avg_rate": int(round(float(data.avg_rate or 0))),
            "url": url,
            "source": "live",
        }

    upwork = results.get("upwork")
    fiverr = results.get("fiverr")
    contra = results.get("contra")

    plat = {
        "upwork": _one("upwork", upwork, f"https://www.upwork.com/nx/search/jobs/?q={query}"),
        "fiverr": _one("fiverr", fiverr, f"https://www.fiverr.com/search/gigs?query={query}"),
        "contra": _one("contra", contra, f"https://contra.com/search?q={query}"),
    }

    total_jobs = sum(p["jobs"] for p in plat.values())
    rates = [p["avg_rate"] for p in plat.values() if p["jobs"] > 0 and p["avg_rate"] > 0]
    avg_rate = sum(rates) / len(rates) if rates else 0

    # Same viability formula as demand_refresh (simplified)
    import math
    job_score = min(30, int(10 * math.log10(max(total_jobs, 1) + 1)))
    rate_score = min(25, int(avg_rate / 4))
    n_valid = sum(1 for p in plat.values() if p["jobs"] > 0)
    diversity = min(10, n_valid * 3)
    score = min(100, 20 + job_score + rate_score + diversity + (15 if total_jobs > 500 else 8))

    return {
        **plat,
        "demand_score": score,
        "trend": "growing" if total_jobs > 500 else "stable" if total_jobs > 100 else "declining",
        "estimated_time_to_gig": f"{max(1, 5 - score // 20)} weeks",
        "difficulty": "Beginner" if score < 30 else "Intermediate" if score < 60 else "Advanced",
        "data_source": "live",
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "stale": False,
    }


def cache_scrape_to_intelligence(sb, slug: str, scrape_results: dict, platform_ui: dict) -> None:
    """Persist a fresh scrape into topic_intelligence so next request is instant."""
    try:
        breakdown: dict[str, Any] = {}
        total_jobs = 0
        weighted_rate_num = 0.0
        weighted_rate_den = 0.0
        weights = {"upwork": 1.0, "fiverr": 0.8, "contra": 0.6}

        for name, data in (scrape_results or {}).items():
            if data is None or isinstance(data, Exception):
                continue
            if (data.job_count or 0) <= 0:
                continue
            breakdown[name] = {
                "job_count": int(data.job_count),
                "avg_rate": float(data.avg_rate or 0),
                "trend": getattr(data, "trend", "stable"),
            }
            total_jobs += int(data.job_count)
            w = weights.get(name, 0.5)
            weighted_rate_num += float(data.avg_rate or 0) * int(data.job_count) * w
            weighted_rate_den += int(data.job_count) * w

        if total_jobs <= 0:
            return

        avg_rate = weighted_rate_num / weighted_rate_den if weighted_rate_den else 0
        now = datetime.now(timezone.utc).isoformat()
        row = {
            "topic": slug,
            "freelance_job_count": total_jobs,
            "avg_rate": round(avg_rate, 2),
            "demand_trend": platform_ui.get("trend", "stable"),
            "viability_score": platform_ui.get("demand_score", 50),
            "last_updated": now,
            "platform_breakdown": breakdown,
        }
        try:
            sb.table("topic_intelligence").upsert(row, on_conflict="topic").execute()
        except Exception as e:
            # Column may not exist yet — drop platform_breakdown and retry
            if "platform_breakdown" in str(e):
                row.pop("platform_breakdown", None)
                sb.table("topic_intelligence").upsert(row, on_conflict="topic").execute()
            else:
                raise

        # Keep topics table in sync so other readers (admin, seeds) see fresh numbers
        try:
            sb.table("topics").update({
                "job_count": total_jobs,
                "avg_rate": round(avg_rate, 2),
                "demand_score": platform_ui.get("demand_score", 50),
            }).eq("slug", slug).execute()
        except Exception as e:
            logger.debug(f"topics table sync skipped: {e}")
    except Exception as e:
        logger.warning(f"cache_scrape_to_intelligence failed for {slug}: {e}")
