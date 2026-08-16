"""proposals blueprint — First-Bid challenge + human-initiated submission (eng-spec §3 J6)."""
from flask import Blueprint, render_template, request, redirect, url_for, g

from routes import require_login, load_sprint, load_cluster
from services.supabase_client import get_supabase
from services.verification_service import gate_b_passed
from services.proposal_engine import generate_drafts, list_proposals, verified_platforms, template as proposal_template
from services.iteration_engine import diagnose

proposals_bp = Blueprint("proposals", __name__)

# Outcome type → sprint counter column (eng-spec §4.3: the proposal iteration
# loop writes responses/interviews).
OUTCOME_COLUMNS = {
    "response": "responses_received",
    "interview": "interviews_held",
    "offer": "offers_received",
}


@proposals_bp.route("/sprints/<sprint_id>/proposals")
def index(sprint_id):
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("main.dashboard"))

    # Phase C stays locked until the Mock Contract passes verification.
    if not gate_b_passed(sb, sprint_id):
        return render_template("proposals.html", locked=True, sprint=sprint), 200

    cluster = load_cluster(sb, sprint["cluster_key"])
    generate_drafts(sb, sprint, sprint["cluster_key"], sprint["user_id"])
    proposals = list_proposals(sb, sprint, sprint["cluster_key"])
    submitted_count = sum(1 for p in proposals if p["status"] == "submitted")
    verified = verified_platforms(sb, sprint["user_id"])

    # The iteration loop (eng-spec §4.3): 5 proposals sent, 0 responses →
    # diagnose the bottleneck from the sprint's own data. Rendered on the page
    # so the learner sees the assigned fix without a separate Day-14 step.
    diagnosis = None
    if (sprint.get("proposals_sent") or 0) >= 5 and (sprint.get("responses_received") or 0) == 0:
        diagnosis = diagnose(sprint)

    return render_template(
        "proposals.html", sprint=sprint, proposals=proposals,
        submitted_count=submitted_count,
        template=proposal_template(sprint, cluster),
        verified_platform=verified[0] if verified else "upwork",
        diagnosis=diagnosis,
    )


@proposals_bp.route("/sprints/<sprint_id>/proposals/<proposal_id>/submit", methods=["POST"])
def submit(sprint_id, proposal_id):
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("main.dashboard"))

    platform = request.form.get("platform", "").strip()
    verified = verified_platforms(sb, sprint["user_id"])
    if not platform and verified:
        platform = verified[0]

    # Human-initiated only: submission on an unverified platform is rejected.
    if platform not in verified:
        return redirect(url_for("proposals.index", sprint_id=sprint_id))

    sb.table("proposals").update({
        "status": "submitted", "platform": platform,
    }).eq("id", proposal_id).eq("sprint_id", sprint_id).execute()

    # Increment proposals_sent (real Supabase doesn't support SQL-ish "col + 1";
    # read current value, increment, write back)
    sprint_rows = sb.table("sprints").select("proposals_sent").eq("id", sprint_id).limit(1).execute().data
    if sprint_rows:
        current = sprint_rows[0].get("proposals_sent") or 0
        sb.table("sprints").update({"proposals_sent": current + 1}).eq("id", sprint_id).execute()
    return redirect(url_for("proposals.index", sprint_id=sprint_id))


@proposals_bp.route("/sprints/<sprint_id>/proposals/<proposal_id>/respond", methods=["POST"])
def respond(sprint_id, proposal_id):
    """Human-logged outcome from a submitted proposal: response / interview /
    offer → writes the sprint's outcome counter (eng-spec §4.3)."""
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("main.dashboard"))

    column = OUTCOME_COLUMNS.get(request.form.get("outcome", "").strip().lower())
    if column:
        rows = sb.table("sprints").select(column).eq("id", sprint_id).limit(1).execute().data
        if rows:
            current = rows[0].get(column) or 0
            sb.table("sprints").update({column: current + 1}).eq("id", sprint_id).execute()
    return redirect(url_for("proposals.index", sprint_id=sprint_id))
