"""
contract blueprint — Mock Contract brief + verification gate (arch §4.2, eng-spec §3 J5).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from routes import require_login, load_sprint, load_brief
from services.supabase_client import get_supabase
from services.verification_service import record as record_review

contract_bp = Blueprint("contract", __name__)

DEFAULT_BRIEF = {
    "title": "Set up email automation for my e-commerce brand",
    "requirements": (
        "Klaviyo checkout recovery + post-purchase upsell\n"
        "Segmentation for VIP repeat buyers\n"
        "Deliverables: flow exports + setup docs\n"
        "Must be mobile-responsive emails"
    ),
    "constraints": {"deadline_days": 4, "budget": 180, "notes": ["Client prefers async updates"]},
    "acceptance_criteria": ["flow exports present", "setup docs present", "mobile-responsive"],
    "verification_type": "auto",
}


def _get_job_feed_id(sb, cluster_key):
    """Get a real job_feed.id for the given cluster."""
    rows = sb.table("job_feed").select("id").eq("cluster_key", cluster_key).eq("status", "active").limit(1).execute().data
    return rows[0]["id"] if rows else None


@contract_bp.route("/sprints/<sprint_id>/contract")
def brief(sprint_id):
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("main.dashboard"))
    brief_row = load_brief(sb, sprint_id)
    if not brief_row:
        # Synthesize a default anonymized brief so the mockup screen always renders.
        brief_row = dict(DEFAULT_BRIEF)
        import uuid as _uuid
        brief_row["id"] = str(_uuid.uuid4())
        brief_row["sprint_id"] = sprint_id
        # Get a real job from the job_feed for this cluster
        job_feed_id = _get_job_feed_id(sb, sprint.get("cluster_key", "email-automation"))
        brief_row["job_feed_id"] = job_feed_id
        sb.table("capstone_briefs").insert(brief_row).execute()

    requirements = (brief_row.get("requirements") or "").split("\n")
    constraints = brief_row.get("constraints") or {"deadline_days": 4, "budget": 180, "notes": []}
    if isinstance(constraints, str):
        constraints = {"deadline_days": 4, "budget": 180, "notes": []}
    brief_row["requirements_list"] = [r for r in requirements if r.strip()]
    brief_row["constraints"] = constraints
    return render_template("mock_contract.html", sprint=sprint, brief=brief_row)


@contract_bp.route("/sprints/<sprint_id>/contract/submit", methods=["POST"])
def submit(sprint_id):
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("main.dashboard"))

    url = request.form.get("submission_url", "").strip()
    if not url:
        flash("Paste a link to your deliverable before submitting.")
        return redirect(url_for("contract.brief", sprint_id=sprint_id))

    record_review(sb, sprint_id, "B", status="pending", submitted_url=url)
    flash("Deliverable submitted — verification service is checking your flow.")
    return redirect(url_for("contract.brief", sprint_id=sprint_id))