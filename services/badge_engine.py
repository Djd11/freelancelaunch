"""
Badge Engine — Demand-Validated Badges.

Issues a badge only when the sprint completed AND the Mock Contract passed
verification. Records jobs_at_issue at the moment of issue. Exposes the
live counter read from job_clusters.
"""
import logging
from services.supabase_client import get_supabase
from services.demand_intelligence import live_counter

logger = logging.getLogger(__name__)


def issue(sb=None, sprint_id=None, user_id=None):
    """Issue a badge if eligible. Returns the badge dict or None."""
    sb = sb or get_supabase()
    sprint = sb.table("sprints").select("*").eq("id", sprint_id).eq("user_id", user_id).limit(1).execute()
    if not sprint.data:
        return None
    sprint = sprint.data[0]

    from services.verification_service import is_passed
    if not is_passed(sb, sprint_id, user_id):
        logger.info("Badge withheld: Mock Contract not verified")
        return None

    cluster = sprint.get("cluster_key")
    jobs = live_counter(sb, cluster).get("jobs", 0)

    existing = sb.table("badges").select("id").eq("user_id", user_id).eq("cluster_key", cluster).limit(1).execute()
    if existing.data:
        return existing.data[0]

    badge = sb.table("badges").insert({
        "user_id": user_id,
        "cluster_key": cluster,
        "sprint_id": sprint_id,
        "jobs_at_issue": jobs,
    }).execute()
    badge_id = badge.data[0]["id"] if badge.data else None
    sb.table("sprints").update({"status": "completed", "badge_id": badge_id}).eq("id", sprint_id).execute()
    return badge.data[0] if badge.data else None


def for_user(sb=None, user_id=None):
    """Return the user's badges with live job counts."""
    sb = sb or get_supabase()
    resp = sb.table("badges").select("*").eq("user_id", user_id).execute()
    badges = resp.data or []
    for b in badges:
        b["jobs_now"] = live_counter(sb, b.get("cluster_key")).get("jobs", 0)
    return badges
