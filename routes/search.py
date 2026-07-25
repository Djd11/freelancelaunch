"""
Topic Search routes — search freelance platforms for demand data
"""
import logging
from flask import Blueprint, render_template, request, jsonify, g, url_for
from services.supabase_client import get_supabase
from routes.topics import CURATED_TOPICS

search_bp = Blueprint("search", __name__, url_prefix="/search")
logger = logging.getLogger(__name__)


@search_bp.route("/api", methods=["GET"])
def search_api():
    """Search for a topic across freelance platforms.
    Returns demand data if found, or suggests alternatives."""
    query = request.args.get("q", "").strip().lower()
    if not query or len(query) < 2:
        return jsonify({"error": "Query too short", "results": []})
    
    # Check curated topics first (instant match)
    curated_matches = [t for t in CURATED_TOPICS if query in t["name"].lower() or query in t["slug"]]
    
    # Build response
    response = {
        "query": query,
        "curated_matches": curated_matches[:3],
        "platform_results": _get_platform_demand_data(query),
        "curated_count": len(curated_matches),
    }
    
    # Check if user has platforms linked for the W1 scenario
    from services.supabase_client import get_supabase
    if g.user:
        try:
            sb = get_supabase()
            plat_resp = sb.table("user_platforms").select("id").eq("user_id", g.user["id"]).limit(1).execute()
            response["platforms_linked"] = len(plat_resp.data or []) > 0
        except Exception:
            response["platforms_linked"] = False
    else:
        response["platforms_linked"] = False
    
    return jsonify(response)


@search_bp.route("/suggestions")
def suggestions():
    """Return popular topic suggestions for the search autocomplete."""
    suggestions = [
        {"name": t["name"], "slug": t["slug"], "jobs": t["job_count"], "rate": t["avg_rate"]}
        for t in CURATED_TOPICS
    ]
    # Add some common freelance topics
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
    suggestions.extend(extras)
    return jsonify(suggestions)


def _get_platform_demand_data(query: str) -> dict:
    """Get freelance demand data for a query across platforms.
    MVP: uses heuristic data based on keywords.
    Phase 3: will use Playwright scraper for live data."""
    
    # Heuristic demand scoring based on keywords
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
    
    # Base score for any query
    score = max(10, min(95, score + len(query) * 2))
    
    # Simulate platform data
    job_count = int(score * 15 + len(query) * 3)
    avg_rate = 15 + int(score * 0.4)
    
    return {
        "upwork": {
            "status": "available",
            "jobs": job_count,
            "avg_rate": avg_rate,
            "url": f"https://www.upwork.com/search/jobs/?q={query}",
        },
        "fiverr": {
            "status": "available",
            "jobs": int(job_count * 1.5),
            "avg_rate": max(10, avg_rate - 5),
            "url": f"https://www.fiverr.com/search/gigs?query={query}",
        },
        "contra": {
            "status": "available",
            "jobs": int(job_count * 0.3),
            "avg_rate": avg_rate + 5,
            "url": f"https://contra.com/search?q={query}",
        },
        "demand_score": score,
        "trend": "growing" if score > 50 else "stable",
        "estimated_time_to_gig": f"{max(1, 5 - score//20)} weeks",
        "difficulty": "Beginner" if score < 30 else "Intermediate" if score < 60 else "Advanced",
    }


@search_bp.route("/curriculum/<slug>")
def get_curriculum(slug):
    """API: fetch curriculum days for a topic."""
    from services.supabase_client import get_supabase
    try:
        sb = get_supabase()
        t = sb.table("topics").select("id").eq("slug", slug).limit(1).execute()
        if not t.data: return jsonify({"days":[]})
        c = sb.table("curricula").select("id").eq("topic_id", t.data[0]["id"]).limit(1).execute()
        if not c.data: return jsonify({"days":[]})
        d = sb.table("curriculum_days").select("*").eq("curriculum_id",c.data[0]["id"]).order("day_number").limit(30).execute()
        return jsonify({"days": d.data or [], "count": len(d.data or [])})
    except Exception as e:
        return jsonify({"error": str(e), "days": []})
