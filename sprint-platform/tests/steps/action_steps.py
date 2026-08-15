"""Action + verify steps — form submissions, DB-state assertions, iteration diagnosis."""
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