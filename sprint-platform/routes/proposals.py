"""proposals blueprint — First-Bid challenge + human-initiated submission (eng-spec §3 J6)."""
from flask import Blueprint, render_template, request, redirect, url_for, g

from routes import require_login, load_sprint, load_cluster
from services.supabase_client import get_supabase
from services.verification_service import gate_b_passed
from services.proposal_engine import generate_drafts, list_proposals, verified_platforms, template as proposal_template

proposals_bp = Blueprint("proposals", __name__)


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
    return render_template(
        "proposals.html", sprint=sprint, proposals=proposals,
        submitted_count=submitted_count,
        template=proposal_template(sprint, cluster),
        verified_platform=verified[0] if verified else "upwork",
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
