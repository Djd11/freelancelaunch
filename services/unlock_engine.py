"""
Unlock Engine — Job Unlock Meter

Recomputes how many live job postings a user has unlocked after each
completed sprint day, and writes a sprint_unlock_snapshots row so the
meter renders in O(1).

unlocked = COUNT(job_feed WHERE cluster_key = <sprint> AND unlock_day <= completed_days)
"""
import logging
from services.supabase_client import get_supabase

logger = logging.getLogger(__name__)


def recompute(sb=None, sprint_id=None, user_id=None):
    """Recompute the meter for a sprint. Returns the meter dict.

    Returns {completed_days, unlocked, total, newly_unlocked} or None on failure.
    """
    sb = sb or get_supabase()
    try:
        sprint = sb.table("sprints").select("cluster_key,current_day").eq("id", sprint_id).limit(1).execute()
        if not sprint.data:
            return None
        cluster_key = sprint.data[0]["cluster_key"]
        completed_days = sprint.data[0].get("current_day", 0)

        unlocked_resp = sb.table("job_feed").select("id", count="exact") \
            .eq("cluster_key", cluster_key) \
            .lte("unlock_day", completed_days) \
            .eq("status", "active").execute()
        unlocked = getattr(unlocked_resp, "count", None) or len(unlocked_resp.data or [])

        total_resp = sb.table("job_feed").select("id", count="exact") \
            .eq("cluster_key", cluster_key).eq("status", "active").execute()
        total = getattr(total_resp, "count", None) or len(total_resp.data or [])

        # Previous snapshot for the delta (fast read)
        prev = 0
        prev_resp = sb.table("sprint_unlock_snapshots").select("unlocked_count") \
            .eq("sprint_id", sprint_id).eq("user_id", user_id).limit(1).execute()
        if prev_resp.data:
            prev = prev_resp.data[0].get("unlocked_count", 0)

        newly = unlocked - prev

        sb.table("sprint_unlock_snapshots").upsert({
            "sprint_id": sprint_id,
            "user_id": user_id,
            "completed_days": completed_days,
            "unlocked_count": unlocked,
            "total_in_cluster": total,
            "last_delta": newly,
        }, on_conflict="sprint_id,user_id").execute()

        return {
            "completed_days": completed_days,
            "unlocked": unlocked,
            "total": total,
            "newly_unlocked": newly,
        }
    except Exception as e:
        logger.warning(f"unlock_engine.recompute failed: {e}")
        return None


def read_meter(sb=None, sprint_id=None, user_id=None):
    """Read the meter from the snapshot (O(1)). Falls back to live recompute."""
    sb = sb or get_supabase()
    try:
        resp = sb.table("sprint_unlock_snapshots").select("*") \
            .eq("sprint_id", sprint_id).eq("user_id", user_id).limit(1).execute()
        if resp.data:
            row = resp.data[0]
            return {
                "completed_days": row.get("completed_days", 0),
                "unlocked": row.get("unlocked_count", 0),
                "total": row.get("total_in_cluster", 0),
                "newly_unlocked": row.get("last_delta", 0),
            }
    except Exception as e:
        logger.warning(f"read_meter failed: {e}")
    return recompute(sb, sprint_id, user_id)
