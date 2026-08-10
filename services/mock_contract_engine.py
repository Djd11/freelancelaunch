"""
Mock Contract Engine — Phase B (Days 6-10)

Derives a capstone brief from a real, anonymized job_feed posting and
enforces deadline/constraints. The brief references only job_feed_id,
never client PII.
"""
import logging
from services.supabase_client import get_supabase

logger = logging.getLogger(__name__)

DEFAULT_CONSTRAINTS = {"deadline_days": 4, "budget": 180, "async_updates": True}


def create_brief(sb=None, sprint_id=None, user_id=None):
    """Pick a matching job_feed posting and create a capstone brief."""
    sb = sb or get_supabase()
    sprint = sb.table("sprints").select("cluster_key").eq("id", sprint_id).limit(1).execute()
    if not sprint.data:
        return None
    cluster_key = sprint.data[0]["cluster_key"]

    existing = sb.table("capstone_briefs").select("*").eq("sprint_id", sprint_id).limit(1).execute()
    if existing.data:
        return existing.data[0]

    # Pick the highest-value posting not yet used as a brief for this cluster
    job = sb.table("job_feed").select("*").eq("cluster_key", cluster_key) \
        .order("unlock_day", desc=True).limit(1).execute()
    if not job.data:
        return None
    posting = job.data[0]

    brief = sb.table("capstone_briefs").insert({
        "sprint_id": sprint_id,
        "job_feed_id": posting["id"],
        "title": f"Client Brief · {posting['title']}",
        "requirements": posting.get("description", ""),
        "constraints": DEFAULT_CONSTRAINTS,
        "acceptance_criteria": [
            "Deliverable matches the brief requirements",
            "Handled within the deadline window",
            "Mobile/quality pass per rubric",
        ],
        "verification_type": "auto" if posting.get("skills", []) and "code" in str(posting.get("skills", [])) else "peer",
    }).execute()
    return brief.data[0] if brief.data else None
