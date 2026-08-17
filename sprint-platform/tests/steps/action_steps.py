"""Action + verify steps — form submissions, DB-state assertions, iteration diagnosis."""
import json

from behave import when, then

from tests.live_db_adapter import get_live_adapter, TEST_USER_ID, get_static_job_id
from tests.steps.common_steps import _post
from services.iteration_engine import diagnose


# ── When: form submissions ─────────────────────────────────────────
@when('I POST to "{path}"')
def step_post_plain(context, path):
    _post(context, path, data={})


@when('I POST the login form with email "{email}"')
def step_login_form(context, email):
    _post(context, "/auth/login", data={"email": email})


@when('I submit a request-a-sprint form for skill "{skill}"')
def step_request_sprint(context, skill):
    _post(context, "/sprints/request", data={"skill": skill})


@when('I submit the copy-work task for day {day} of sprint "{sid}" with rubric_url "{url}"')
def step_copywork_submit(context, day, sid, url):
    _post(context, f"/sprints/{sid}/day/{day}/copywork", data={"rubric_url": url})


@when('the content generation worker runs for sprint "{sid}"')
def step_worker_run(context, sid):
    """Run the async content worker synchronously, forcing the deterministic
    fallbacks (no real LLM/TTS in tests) so assertions are stable."""
    import services.lesson_engine as le
    import services.video_engine as ve
    le.call_llm = lambda *a, **k: None
    ve.voiceover_for_lesson = lambda *a, **k: None
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    le.generate_sprint_content(adapter.sb, real_sprint_id)


@when('I submit the contract form to "{path}" with no data')
def step_contract_no_data(context, path):
    _post(context, path, data={})


@when('I submit the contract form to "{path}" with submission_url "{url}"')
def step_contract_submit(context, path, url):
    _post(context, path, data={"submission_url": url})


@when('I submit the proposal form to "{path}"')
def step_proposal_submit(context, path):
    _post(context, path, data={})


@when('I choose platform "{platform}" and submit the proposal form to "{path}"')
def step_proposal_platform(context, platform, path):
    _post(context, path, data={"platform": platform})


@when('I add a contract of value {value:d} with {hours:d} hours on platform "{platform}" for sprint "{sid}"')
def step_add_contract(context, value, hours, platform, sid):
    _post(context, f"/sprints/{sid}/contract/add", data={
        "client_name": "Demo Client",
        "project_title": "Email automation setup",
        "contract_value": value,
        "hours_worked": hours,
        "platform": platform,
    })


@when('I log outcome "{outcome}" for proposal "{pid}" on sprint "{sid}"')
def step_log_outcome(context, outcome, pid, sid):
    _post(context, f"/sprints/{sid}/proposals/{pid}/respond", data={"outcome": outcome})


@when('I mark the most recent contract complete for sprint "{sid}"')
def step_contract_complete(context, sid):
    """POST to /sprints/<id>/contract/<cid>/complete for the sprint's newest
    contract (the dashboard "Mark complete" CTA on each active contract row)."""
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("contracts").select("id") \
        .eq("sprint_id", real_sprint_id).order("created_at", desc=True).limit(1).execute().data
    assert rows, f"no contracts for sprint {sid} to mark complete"
    _post(context, f"/sprints/{sid}/contract/{rows[0]['id']}/complete", data={})


@when('I save the case study "{title}" for sprint "{sid}"')
def step_save_case_study(context, title, sid):
    _post(context, f"/sprints/{sid}/case-study", data={
        "title": title,
        "problem": "Store lost checkouts to cart abandonment.",
        "solution": "Built a 2-step recovery flow with a dynamic cart summary.",
        "result": "Recovered 12% of abandoned carts in 4 weeks.",
    })


@then('gate "{gate}" has passed verification for sprint "{sid}"')
def step_gate_passed(context, gate, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("verification_reviews").select("*") \
        .eq("sprint_id", real_sprint_id).eq("gate", gate).execute().data
    assert rows and rows[0].get("status") == "pass", \
        f"gate {gate} not passed for sprint {sid}: {rows}"


@then('gate "{gate}" has not passed verification for sprint "{sid}"')
def step_gate_not_passed(context, gate, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("verification_reviews").select("*") \
        .eq("sprint_id", real_sprint_id).eq("gate", gate).execute().data
    assert not rows or rows[0].get("status") != "pass", \
        f"gate {gate} unexpectedly passed for sprint {sid}: {rows}"


@then('copy-work project {n} for sprint "{sid}" is not marked done')
def step_project_not_done(context, n, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("copywork_projects").select("done") \
        .eq("sprint_id", real_sprint_id).eq("project_index", int(n)).execute().data
    assert rows and not rows[0].get("done"), \
        f"copy-work project {n} unexpectedly done for sprint {sid}: {rows}"


@then('copy-work project {n} for sprint "{sid}" has submitted_url "{url}"')
def step_project_has_url(context, n, sid, url):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("copywork_projects").select("submitted_url") \
        .eq("sprint_id", real_sprint_id).eq("project_index", int(n)).execute().data
    assert rows and rows[0].get("submitted_url") == url, \
        f"copy-work project {n} submitted_url={rows[0].get('submitted_url') if rows else None!r}, expected {url!r}"


@then('copy-work project {n} for sprint "{sid}" has a title mentioning "{text}"')
def step_project_title_mentions(context, n, sid, text):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("copywork_projects").select("title") \
        .eq("sprint_id", real_sprint_id).eq("project_index", int(n)).execute().data
    assert rows, f"no copy-work project {n} for sprint {sid}"
    assert text in rows[0].get("title", ""), \
        f"project {n} title {rows[0].get('title')!r} does not mention {text!r}"


@then('day {n} of sprint "{sid}" has a lesson mentioning "{text}"')
def step_day_lesson_mentions(context, n, sid, text):
    """Assert the worker stored a lesson whose content mentions the text —
    e.g. the Day 5 gap-fill micro-lesson targeting the flagged nuance."""
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("sprint_days").select("action_payload") \
        .eq("sprint_id", real_sprint_id).eq("day_no", int(n)).execute().data
    assert rows, f"no day {n} row for sprint {sid}"
    lesson = (rows[0].get("action_payload") or {}).get("lesson") or {}
    blob = json.dumps(lesson)
    assert text in blob, f"day {n} lesson missing {text!r}: {blob}"


def _sprint_row(context, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("sprints").select("*").eq("id", real_sprint_id).execute().data
    assert rows, f"no sprint {sid}"
    return rows[0]


@then('sprint "{sid}" has contracts_won equal to {n:d}')
def step_contracts_won(context, sid, n):
    row = _sprint_row(context, sid)
    assert int(row.get("contracts_won") or 0) == n, \
        f"contracts_won={row.get('contracts_won')}, expected {n}"


@then('sprint "{sid}" has contracts_completed equal to {n:d}')
def step_contracts_completed(context, sid, n):
    row = _sprint_row(context, sid)
    assert int(row.get("contracts_completed") or 0) == n, \
        f"contracts_completed={row.get('contracts_completed')}, expected {n}"


@then('sprint "{sid}" has total_earned equal to {n:d}')
def step_total_earned(context, sid, n):
    row = _sprint_row(context, sid)
    assert int(row.get("total_earned") or 0) == n, \
        f"total_earned={row.get('total_earned')}, expected {n}"


@then('sprint "{sid}" has avg_contract_value equal to {n:d}')
def step_avg_contract_value(context, sid, n):
    row = _sprint_row(context, sid)
    assert int(row.get("avg_contract_value") or 0) == n, \
        f"avg_contract_value={row.get('avg_contract_value')}, expected {n}"


@then('sprint "{sid}" has a first_contract_at timestamp')
def step_first_contract_at(context, sid):
    row = _sprint_row(context, sid)
    assert row.get("first_contract_at"), f"first_contract_at missing: {row.get('first_contract_at')!r}"


@then('sprint "{sid}" is completed')
def step_sprint_completed(context, sid):
    row = _sprint_row(context, sid)
    assert row.get("status") == "completed", \
        f"sprint {sid} status={row.get('status')}, expected completed"


@then('sprint "{sid}" has responses_received equal to {n:d}')
def step_responses_received(context, sid, n):
    row = _sprint_row(context, sid)
    assert int(row.get("responses_received") or 0) == n, \
        f"responses_received={row.get('responses_received')}, expected {n}"


@then('a case study titled "{title}" exists for sprint "{sid}"')
def step_case_study_exists(context, title, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("case_studies").select("*") \
        .eq("sprint_id", real_sprint_id).eq("title", title).execute().data
    assert rows, f"no case study {title!r} for sprint {sid}"


@when('the sprint reaches day {n}')
def step_sprint_reaches_day(context, n):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id("s1")
    adapter.sb.table("sprints").update({
        "current_day": int(n),
        "phase": "C" if int(n) >= 11 else "A",
    }).eq("id", real_sprint_id).execute()
    # Get the updated sprint for diagnosis
    sprint = adapter.sb.table("sprints").select("*").eq("id", real_sprint_id).limit(1).execute().data[0]
    context.diagnosis = diagnose(sprint)


# ── Then: DB-state assertions ──────────────────────────────────────
@then('a verification review for gate "{gate}" is recorded for sprint "{sid}"')
def step_review_recorded(context, gate, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("verification_reviews").select("*").eq("sprint_id", real_sprint_id).eq("gate", gate).execute().data
    assert rows, f"no verification_reviews row for ({sid}, gate {gate})"


@then('a job cluster "{key}" is recorded as requested')
def step_cluster_requested(context, key):
    adapter = get_live_adapter()
    rows = adapter.sb.table("job_clusters").select("*").eq("cluster_key", key).eq("status", "requested").execute().data
    assert rows, f"cluster {key} not recorded as requested"


@then('a badge is issued for sprint "{sid}"')
def step_badge_issued(context, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("badges").select("*").eq("sprint_id", real_sprint_id).execute().data
    assert rows, f"no badge row for sprint {sid}"


@then('no badge is issued for sprint "{sid}"')
def step_badge_not_issued(context, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("badges").select("*").eq("sprint_id", real_sprint_id).execute().data
    assert not rows, f"unexpected badge row for sprint {sid}: {rows}"


@then('draft proposals exist for sprint "{sid}"')
def step_drafts_exist(context, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("proposals").select("*").eq("sprint_id", real_sprint_id).eq("status", "draft").execute().data
    assert rows, f"no draft proposals for sprint {sid}"


@then('the proposal "{pid}" is marked submitted')
def step_proposal_submitted(context, pid):
    adapter = get_live_adapter()
    real_pid = adapter.get_proposal_real_id(pid)
    rows = adapter.sb.table("proposals").select("*").eq("id", real_pid).execute().data
    assert rows and rows[0].get("status") == "submitted", f"proposal {pid} not submitted: {rows}"


@then('the proposal "{pid}" is submitted on platform "{platform}"')
def step_proposal_platform_status(context, pid, platform):
    adapter = get_live_adapter()
    real_pid = adapter.get_proposal_real_id(pid)
    rows = adapter.sb.table("proposals").select("*").eq("id", real_pid).execute().data
    assert rows, f"no proposal {pid}"
    assert rows[0].get("status") == "submitted", f"proposal {pid} not submitted"
    assert rows[0].get("platform") == platform, \
        f"proposal {pid} platform={rows[0].get('platform')}, expected {platform}"


@then('sprint "{sid}" has proposals_sent equal to {n}')
def step_sprint_sent(context, sid, n):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("sprints").select("*").eq("id", real_sprint_id).execute().data
    assert rows, f"no sprint {sid}"
    assert rows[0].get("proposals_sent") == int(n), \
        f"proposals_sent={rows[0].get('proposals_sent')}, expected {n}"


@then('the proposal "{pid}" remains a draft until the user confirms submission')
def step_proposal_draft_confirm(context, pid):
    adapter = get_live_adapter()
    real_pid = adapter.get_proposal_real_id(pid)
    rows = adapter.sb.table("proposals").select("*").eq("id", real_pid).execute().data
    assert rows and rows[0].get("status") == "draft", f"proposal {pid} not draft"


@then('the proposal "{pid}" remains a draft')
def step_proposal_draft(context, pid):
    adapter = get_live_adapter()
    real_pid = adapter.get_proposal_real_id(pid)
    rows = adapter.sb.table("proposals").select("*").eq("id", real_pid).execute().data
    assert rows and rows[0].get("status") == "draft", f"proposal {pid} not draft"


@then('the sprint "{sid}" is now on day {n}')
def step_sprint_now_day(context, sid, n):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("sprints").select("*").eq("id", real_sprint_id).execute().data
    assert rows, f"no sprint {sid}"
    assert rows[0].get("current_day") == int(n), \
        f"current_day={rows[0].get('current_day')}, expected {n}"


@then('the iteration engine returns a diagnosis of price, portfolio, or niche')
def step_diagnosis(context):
    assert context.diagnosis in ("price", "portfolio", "niche"), \
        f"diagnosis={context.diagnosis!r}"


@then('the page does not contain any client name')
def step_no_client_name(context):
    html = getattr(context, "page_html", "") or ""
    for bad in ("Acme", "Client Name", "Jordan Lee", "Wayne", "Doe"):
        assert bad not in html, f"page unexpectedly contains client name {bad!r}"


@then('the page does not contain any badge')
def step_no_badge(context):
    html = getattr(context, "page_html", "") or ""
    assert "����" not in html, "page unexpectedly contains a badge"


@then('a mentor session exists for sprint "{sid}" and job "{job}"')
def step_mentor_session(context, sid, job):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    # Map fixture job ID to real UUID using module-level storage
    real_job_id = get_static_job_id(job)
    rows = adapter.sb.table("mentor_sessions").select("*").eq("sprint_id", real_sprint_id).eq("job_feed_id", real_job_id).execute().data
    assert rows, f"no mentor session for ({sid}, {job})"