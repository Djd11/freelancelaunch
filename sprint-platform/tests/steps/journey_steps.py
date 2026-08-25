"""Journey steps — the full end-to-end learner journey over HTTP (eng-spec J1→J7).

The journey sprint is created through the real HTTP surface (POST
/sprints/<cluster>/start), so its UUID is captured from the redirect and used
directly in subsequent requests. It is tracked for cleanup so the live test
project stays clean across re-runs.
"""
import re

from behave import when, then

from tests.live_db_adapter import get_live_adapter
from tests.steps.common_steps import _get, _post
from services.verification_service import record as record_review

_UUID_RE = r"[0-9a-fA-F-]{36}"


def _journey_sprint_id(context):
    sid = getattr(context, "journey_sprint_id", None)
    assert sid, "journey sprint not started yet — run the start step first"
    return sid


@when('I start a sprint for cluster "{cluster}" from the picker')
def step_journey_start(context, cluster):
    resp = _get(context, "/sprints")
    assert resp.status_code == 200, f"picker returned {resp.status_code}"
    assert f"/sprints/{cluster}/start" in context.page_html, \
        f"picker has no start link for {cluster}"
    resp = _post(context, f"/sprints/{cluster}/start", data={})
    assert resp.status_code == 302, f"start returned {resp.status_code}, expected 302"
    loc = resp.headers.get("Location", "")
    m = re.search(rf"/sprints/({_UUID_RE})$", loc)
    assert m, f"no sprint UUID in redirect Location: {loc!r}"
    context.journey_sprint_id = m.group(1)
    # Track the app-created sprint so after_scenario cleanup removes it
    # (children — days, snapshots, briefs, proposals, reviews, badge — cascade).
    get_live_adapter().track_created("sprints", context.journey_sprint_id)


@when('I open the journey dashboard')
def step_journey_dashboard(context):
    _get(context, f"/sprints/{_journey_sprint_id(context)}")


@when('I open the journey contract')
def step_journey_contract(context):
    _get(context, f"/sprints/{_journey_sprint_id(context)}/contract")


@when('I open the journey proposals page')
def step_journey_proposals(context):
    _get(context, f"/sprints/{_journey_sprint_id(context)}/proposals")


@when('I complete day {n} of the journey sprint')
def step_journey_complete_day(context, n):
    # Models the AJAX/API client of the dual-mode day-complete endpoint
    # (eng-spec J3): browser form POSTs redirect (PRG), API callers that want
    # the meter payload send X-Requested-With and receive JSON.
    _post(context, f"/sprints/{_journey_sprint_id(context)}/day/{int(n)}/complete",
          data={}, headers={"X-Requested-With": "XMLHttpRequest"})


@when('I submit copy-work for day {n} of the journey sprint with rubric_url "{url}"')
def step_journey_copywork(context, n, url):
    _post(context, f"/sprints/{_journey_sprint_id(context)}/day/{int(n)}/copywork",
          data={"rubric_url": url})


@when('the verification service passes gate "{gate}" for the journey sprint')
def step_journey_gate_pass(context, gate):
    # The verification service is an external actor: it writes the gate result
    # directly (same path the auto-verifier uses in production).
    record_review(get_live_adapter().sb, _journey_sprint_id(context), gate, status="pass")


@when('I submit the journey contract deliverable with submission_url "{url}"')
def step_journey_contract_submit(context, url):
    _post(context, f"/sprints/{_journey_sprint_id(context)}/contract/submit",
          data={"submission_url": url})


@when('I submit the first draft proposal of the journey sprint on platform "{platform}"')
def step_journey_first_proposal(context, platform):
    sid = _journey_sprint_id(context)
    m = re.search(rf"/sprints/{sid}/proposals/({_UUID_RE})/submit", context.page_html)
    assert m, "proposals page has no draft submit form"
    _post(context, f"/sprints/{sid}/proposals/{m.group(1)}/submit", data={"platform": platform})


@when('the journey sprint is marked completed')
def step_journey_completed(context):
    adapter = get_live_adapter()
    adapter.sb.table("sprints").update({
        "status": "completed", "current_day": 14, "phase": "C",
    }).eq("id", _journey_sprint_id(context)).execute()


@when('I request the journey badge')
def step_journey_badge(context):
    _get(context, f"/sprints/{_journey_sprint_id(context)}/badge")


@then('the journey sprint is on day {n}')
def step_journey_on_day(context, n):
    adapter = get_live_adapter()
    rows = adapter.sb.table("sprints").select("current_day") \
        .eq("id", _journey_sprint_id(context)).execute().data
    assert rows, "journey sprint row missing"
    assert rows[0]["current_day"] == int(n), \
        f"journey sprint current_day={rows[0]['current_day']}, expected {n}"


@then('the journey sprint has proposals_sent equal to {n}')
def step_journey_sent(context, n):
    adapter = get_live_adapter()
    rows = adapter.sb.table("sprints").select("proposals_sent") \
        .eq("id", _journey_sprint_id(context)).execute().data
    assert rows, "journey sprint row missing"
    assert rows[0]["proposals_sent"] == int(n), \
        f"proposals_sent={rows[0]['proposals_sent']}, expected {n}"


@then('a badge is issued for the journey sprint')
def step_journey_badge_issued(context):
    adapter = get_live_adapter()
    rows = adapter.sb.table("badges").select("*") \
        .eq("sprint_id", _journey_sprint_id(context)).execute().data
    assert rows, "no badge row for the journey sprint"


@then('a verification review for gate "{gate}" is recorded for the journey sprint')
def step_journey_review_recorded(context, gate):
    adapter = get_live_adapter()
    rows = adapter.sb.table("verification_reviews").select("*") \
        .eq("sprint_id", _journey_sprint_id(context)).eq("gate", gate).execute().data
    assert rows, f"no verification_reviews row for the journey sprint gate {gate}"


@when('I start the sprint again from the picker')
def step_start_sprint_again(context):
    """Idempotency: re-POST /sprints/<cluster>/start (eng-spec J2). The route must
    redirect to the SAME sprint UUID instead of 500 or creating a duplicate."""
    resp = _post(context, "/sprints/email-automation/start", data={})
    loc = resp.headers.get("Location", "")
    m = re.search(rf"/sprints/({_UUID_RE})$", loc)
    assert m, f"second start Location has no sprint UUID: {loc!r}"
    context.second_start_uuid = m.group(1)
    get_live_adapter().track_created("sprints", context.second_start_uuid)


@then('the response redirects to the same sprint')
def step_redirects_to_same_sprint(context):
    first = _journey_sprint_id(context)
    second = getattr(context, "second_start_uuid", None)
    assert second, "second start did not capture a sprint UUID"
    assert second == first, \
        f"second start created a new sprint {second} instead of resuming {first}"
