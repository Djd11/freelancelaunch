"""proposals blueprint — First-Bid challenge + human-initiated submission (eng-spec §3 J6)."""
import threading

from flask import Blueprint, render_template, request, redirect, url_for, g

from routes import require_login, load_sprint, load_cluster
from services.supabase_client import get_supabase
from services.verification_service import gate_b_passed
from services.proposal_engine import (SCORE_ERROR, generate_drafts, fill_drafts,
                                      list_proposals, verified_platforms)
from services.iteration_engine import diagnose

proposals_bp = Blueprint("proposals", __name__)

# Thread dedup: at most one fill thread per sprint at any time.
_active_fill_threads = set()
_fill_lock = threading.Lock()


def _should_spawn_fill(sprint_id):
    """Check if we should spawn a new fill thread for this sprint."""
    with _fill_lock:
        if sprint_id in _active_fill_threads:
            return False
        _active_fill_threads.add(sprint_id)
        return True


def _fill_done(sprint_id):
    """Mark a fill thread as done."""
    with _fill_lock:
        _active_fill_threads.discard(sprint_id)

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
    # LLM bodies fill asynchronously — the page shows generating/error states
    # and each load re-fills any failed drafts (self-healing retry).
    # Thread dedup: at most one fill thread per sprint at any time.
    from flask import current_app
    app = current_app._get_current_object()
    if _should_spawn_fill(sprint["id"]):
        threading.Thread(
            target=_fill_in_background, args=(app, sprint["id"], sprint["cluster_key"]), daemon=True,
        ).start()
    proposals = list_proposals(sb, sprint, sprint["cluster_key"])
    submitted_count = sum(1 for p in proposals if p["status"] == "submitted")
    verified = verified_platforms(sb, sprint["user_id"])

    # The Proposal Builder card is the first draft's engineered body (capstone
    # job), with explicit generating / failed states while the LLM fills it.
    first = next((p for p in proposals if p.get("template_body")), None) or (proposals[0] if proposals else None)
    if first and first.get("template_body"):
        proposal_text = first["template_body"]
        proposal_state = "ready"
    elif first and first.get("score") == SCORE_ERROR:
        proposal_text = None
        proposal_state = "error"
    else:
        proposal_text = None
        proposal_state = "generating"

    # The iteration loop (eng-spec §4.3): 5 proposals sent, 0 responses →
    # diagnose the bottleneck from the sprint's own data. Rendered on the page
    # so the learner sees the assigned fix without a separate Day-14 step.
    diagnosis = None
    if (sprint.get("proposals_sent") or 0) >= 5 and (sprint.get("responses_received") or 0) == 0:
        diagnosis = diagnose(sprint)

    return render_template(
        "proposals.html", sprint=sprint, proposals=proposals,
        submitted_count=submitted_count,
        proposal_text=proposal_text, proposal_state=proposal_state,
        verified_platform=verified[0] if verified else "upwork",
        diagnosis=diagnosis,
    )


def _fill_in_background(app, sprint_id, cluster_key):
    """Background LLM proposal fill — app context + dedicated Supabase client.
    Stamps score=-1 on failure; always releases the thread lock."""
    try:
        with app.app_context():
            from supabase import create_client
            sb = create_client(
                app.config.get("SUPABASE_URL") or "",
                app.config.get("SUPABASE_SERVICE_KEY") or app.config.get("SUPABASE_KEY") or "",
            )
            fill_drafts(sb, sprint_id, cluster_key)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("proposal fill failed for %s", sprint_id)
        # Stamp score=-1 on unfilled proposals so the page surfaces the error
        try:
            from supabase import create_client as _cc
            sb = _cc(
                app.config.get("SUPABASE_URL") or "",
                app.config.get("SUPABASE_SERVICE_KEY") or app.config.get("SUPABASE_KEY") or "",
            )
            sb.table("proposals").update({"score": -1, "template_body": None}) \
                .eq("sprint_id", sprint_id).is_("template_body", "null").execute()
        except Exception:
            logging.getLogger(__name__).exception("failed to stamp score=-1 for %s", sprint_id)
    finally:
        _fill_done(sprint_id)


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
