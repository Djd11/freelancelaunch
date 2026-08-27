"""
contract blueprint — Mock Contract brief + verification gate (arch §4.2, eng-spec §3 J5).
Also the sprint's outcome write paths: contract add/complete (eng-spec §5.6)
and the Problem/Solution/Result case study (Days 9-10, J5).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from routes import require_login, load_sprint, load_brief
from services.supabase_client import get_supabase
from services.verification_service import record as record_review
from services.verification_service import auto_check_gate_b, gate_b_passed, is_valid_url
from services.mock_contract_engine import synthesize as synthesize_brief
from services.outcome_service import add_contract, complete_contract

contract_bp = Blueprint("contract", __name__)


def _num(value, cast, default):
    try:
        return cast(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _validate_contract_form(form):
    """Validate contract add form fields. Returns dict of field -> error message."""
    errors = {}
    client_name = (form.get("client_name") or "").strip()
    if not client_name:
        errors["client_name"] = "Client name is required."
    elif len(client_name) > 200:
        errors["client_name"] = "Client name must be under 200 characters."

    try:
        value = float(form.get("contract_value") or 0)
        if value < 0:
            errors["contract_value"] = "Contract value cannot be negative."
        elif value > 1_000_000:
            errors["contract_value"] = "Contract value seems unreasonably high."
    except (TypeError, ValueError):
        errors["contract_value"] = "Contract value must be a number."

    rate = form.get("your_rate")
    if rate not in (None, ""):
        try:
            r = float(rate)
            if r < 0:
                errors["your_rate"] = "Rate cannot be negative."
        except (TypeError, ValueError):
            errors["your_rate"] = "Rate must be a number."

    hours = form.get("hours_worked")
    if hours not in (None, ""):
        try:
            h = int(hours)
            if h < 0:
                errors["hours_worked"] = "Hours cannot be negative."
            elif h > 10000:
                errors["hours_worked"] = "Hours seems unreasonably high."
        except (TypeError, ValueError):
            errors["hours_worked"] = "Hours must be a whole number."

    return errors


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
        # Synthesize an anonymized brief from a real job posting so the mockup
        # screen always renders (No-500). Stores job_feed_id — never client PII.
        brief_row = synthesize_brief(sb, sprint)
        if brief_row.get("job_feed_id"):
            brief_row["sprint_id"] = sprint_id
            sb.table("capstone_briefs").insert(brief_row).execute()
        # else: no feed rows exist at all — render the default brief in-memory.

    requirements = (brief_row.get("requirements") or "").split("\n")
    constraints = brief_row.get("constraints") or {"deadline_days": 4, "budget": 180, "notes": []}
    if isinstance(constraints, str):
        constraints = {"deadline_days": 4, "budget": 180, "notes": []}
    brief_row["requirements_list"] = [r for r in requirements if r.strip()]
    brief_row["constraints"] = constraints

    case_studies = sb.table("case_studies").select("*").eq("sprint_id", sprint_id).execute().data
    # Check if any case study has all 3 fields filled.
    # If gate_b has passed, consider both draft and non-draft case studies.
    # If gate_b hasn't passed yet, only non-draft (published) case studies count.
    gate_b = gate_b_passed(sb, sprint_id)
    case_study_complete = False
    for cs in case_studies:
        if cs.get("problem") and cs.get("solution") and cs.get("result"):
            if gate_b or not cs.get("is_draft"):
                case_study_complete = True
                break

    return render_template("mock_contract.html", sprint=sprint, brief=brief_row,
                           case_studies=case_studies, gate_b_pass=gate_b,
                           case_study_complete=case_study_complete)


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
    if not is_valid_url(url):
        flash("That doesn't look like a valid link — paste the full URL (starting with http:// or https://).")
        return redirect(url_for("contract.brief", sprint_id=sprint_id))

    # The deliverable's own content (or attached artifact text) — the Gate B
    # content check parses it for the rubric-named observable items (P0-2).
    deliverable_text = request.form.get("deliverable_text", "").strip()

    record_review(sb, sprint_id, "B", status="pending", submitted_url=url)
    # Gate B auto-check (arch §7: contract submit → inline auto-test): a valid
    # deliverable URL + a saved case study + (when rubrics exist) the deliverable
    # content containing those artifacts → pass → Phase C unlocks.
    auto_check_gate_b(sb, sprint_id, deliverable_text=deliverable_text)
    flash("Deliverable submitted — verification service is checking your flow.")
    return redirect(url_for("contract.brief", sprint_id=sprint_id))


@contract_bp.route("/sprints/<sprint_id>/contract/add", methods=["POST"])
def add(sprint_id):
    """Record a won contract and roll up earnings on the sprint (eng-spec §5.6)."""
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("main.dashboard"))

    add_contract(
        sb, sprint_id, sprint["user_id"],
        client_name=request.form.get("client_name"),
        project_title=request.form.get("project_title"),
        contract_value=_num(request.form.get("contract_value"), float, 0),
        your_rate=_num(request.form.get("your_rate"), float, None),
        hours_worked=_num(request.form.get("hours_worked"), int, None),
        platform=request.form.get("platform"),
    )
    flash("Contract recorded — earnings rolled up on your sprint.")
    return redirect(url_for("sprints.dashboard", sprint_id=sprint_id))


@contract_bp.route("/sprints/<sprint_id>/contract/<contract_id>/complete", methods=["POST"])
def complete(sprint_id, contract_id):
    """Mark a contract completed; bumps contracts_completed (eng-spec §4.3)."""
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("main.dashboard"))
    complete_contract(sb, sprint_id, contract_id)
    return redirect(url_for("sprints.dashboard", sprint_id=sprint_id))


@contract_bp.route("/sprints/<sprint_id>/case-study", methods=["POST"])
def save_case_study(sprint_id):
    """Write the Problem/Solution/Result case study (Days 9-10). Draft until
    the Mock Contract passes; then it is the profile portfolio item."""
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("main.dashboard"))

    title = request.form.get("title", "").strip()
    if not title:
        flash("Give the case study a title first.")
        return redirect(url_for("contract.brief", sprint_id=sprint_id))

    payload = {
        "sprint_id": sprint_id,
        "user_id": sprint["user_id"],
        "title": title,
        "problem": request.form.get("problem", ""),
        "solution": request.form.get("solution", ""),
        "result": request.form.get("result", ""),
        "is_draft": not gate_b_passed(sb, sprint_id),
    }
    existing = sb.table("case_studies").select("id").eq("sprint_id", sprint_id).limit(1).execute().data
    if existing:
        sb.table("case_studies").update(payload).eq("id", existing[0]["id"]).execute()
    else:
        sb.table("case_studies").insert(payload).execute()
    flash("Case study saved — it appears on your public profile once the Mock Contract passes.")
    return redirect(url_for("contract.brief", sprint_id=sprint_id))
