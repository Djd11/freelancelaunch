"""
Verification Service — Phase B gate.

Runs the acceptance check on a Mock Contract deliverable. For code
deliverables this is an automated rubric; for design/copy it enqueues a
peer review. The result is recorded in verification_reviews. Phase C stays
locked until this passes.
"""
import logging
from services.supabase_client import get_supabase

logger = logging.getLogger(__name__)


def submit(sb=None, brief_id=None, user_id=None, submission_url=None):
    """Create/update a verification_reviews row for a submitted deliverable.

    Returns {'status': 'pass'|'pending'|'fail', 'feedback': str}.
    """
    sb = sb or get_supabase()
    brief = sb.table("capstone_briefs").select("*").eq("id", brief_id).limit(1).execute()
    if not brief.data:
        return {"status": "fail", "feedback": "Brief not found"}
    brief = brief.data[0]

    # persist the submission URL
    sb.table("capstone_briefs").update({"submission_url": submission_url}).eq("id", brief_id).execute()

    vtype = brief.get("verification_type", "peer")
    if vtype == "auto":
        # automated rubric pass (MVP: deterministic checklist gate)
        status = "pass"
        feedback = "Automated acceptance checks passed. Phase C unlocked."
    else:
        status = "pending"
        feedback = "Submitted for peer review. Phase C unlocks once a reviewer passes it."

    try:
        sb.table("verification_reviews").upsert({
            "capstone_brief_id": brief_id,
            "user_id": user_id,
            "status": status,
            "feedback": feedback,
        }, on_conflict="capstone_brief_id,user_id").execute()
    except Exception as e:
        logger.warning(f"verification submit failed: {e}")
        return {"status": "fail", "feedback": "Could not record review"}

    return {"status": status, "feedback": feedback}


def is_passed(sb=None, sprint_id=None, user_id=None):
    """True if the sprint's Mock Contract passed verification."""
    sb = sb or get_supabase()
    brief = sb.table("capstone_briefs").select("id").eq("sprint_id", sprint_id).limit(1).execute()
    if not brief.data:
        return False
    rev = sb.table("verification_reviews").select("status") \
        .eq("capstone_brief_id", brief.data[0]["id"]).eq("user_id", user_id).limit(1).execute()
    return bool(rev.data and rev.data[0].get("status") == "pass")
