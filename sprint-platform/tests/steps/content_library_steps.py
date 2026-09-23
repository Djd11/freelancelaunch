"""Content-library BDD steps (content-library.feature).

Covers the cohort-amortization contract (arch §2 P3): the 14-day course
content is provisioned ONCE per cluster under admin control, every learner
enrolling consumes it with ZERO per-user LLM calls, and clusters without a
library still fall back to the per-sprint LLM worker.

Library rows are tracked for cleanup like every other fixture — the library
is per-cluster shared state, so a leaked row would silently flip later
scenarios (and real enrollments) onto the library path.
"""
import time

from behave import given, when, then

from tests.live_db_adapter import get_live_adapter, OTHER_USER_ID
from tests.steps.common_steps import _get, _post, _login, _html
from tests.steps.action_steps import _fake_generation_llm


# ── Library tracking helper ───────────────────────────────────────────

def _track_library(adapter, cluster_key):
    """Track this cluster's library rows for after_scenario cleanup."""
    rows = adapter.sb.table("cluster_content_library") \
        .select("id").eq("cluster_key", cluster_key).execute().data or []
    for r in rows:
        adapter.track_created("cluster_content_library", r["id"])


# ── Given: library state ──────────────────────────────────────────────

@given('the content library worker has run for cluster "{cluster}"')
@given('the content library worker runs for cluster "{cluster}"')
def step_library_provisioned(context, cluster):
    """Run the REAL admin generation path synchronously with a COUNTING stub
    LLM (deterministic, no live provider). The counter stays installed for the
    whole scenario so any per-user LLM call becomes observable in the
    zero-LLM assertions."""
    from services import content_library
    import services.lesson_engine as le
    import services.video_engine as ve
    adapter = get_live_adapter()
    counter = {"calls": 0}

    def _counting_llm(prompt, **kwargs):
        counter["calls"] += 1
        return _fake_generation_llm(prompt, **kwargs)

    real_llm = le.call_llm
    le.call_llm = _counting_llm
    ve.voiceover_for_lesson = lambda *a, **k: None
    try:
        content_library.generate_for_cluster(adapter.sb, cluster)
    finally:
        context.library_llm_counter = counter
        context.library_llm_baseline = counter["calls"]
        # Keep the counting stub installed (after_scenario restores the real
        # chain) so learner-side calls are counted too.
    _track_library(adapter, cluster)


@given('no content library exists for cluster "{cluster}"')
def step_library_absent(context, cluster):
    """Guarantee the fallback path: remove any library rows for the cluster
    (a prior scenario's leak would otherwise silently feed the new sprint)."""
    adapter = get_live_adapter()
    adapter.sb.table("cluster_content_library") \
        .delete().eq("cluster_key", cluster).execute()


@given('the library lesson for day 4 has already been consumed by a learner')
def step_library_day4_consumed(context):
    """First learner enrolls (library path) and opens day 4 — the 'consumed'
    state the second-learner scenario builds on."""
    context.response = _post(context, "/sprints/email-automation/start", data={})
    assert context.response.status_code == 302
    loc = context.response.headers.get("Location", "")
    assert "/sprints/" in loc
    context.first_sprint_url = loc
    _get(context, f"{loc}/day/4")
    assert context.response.status_code == 200
    context.first_day4_html = _html(context)


@given('a logged-in user with an active sprint "{sid}" for cluster "{cluster}"')
def step_logged_in_with_sprint(context, sid, cluster):
    """Enroll through the REAL start route so the sprint carries exactly what
    production enrollment produces (library-applied content when the library
    is ready), and register the fixture id so later steps resolve it."""
    adapter = get_live_adapter()
    resp = _post(context, f"/sprints/{cluster}/start", data={})
    assert resp.status_code == 302, f"start returned {resp.status_code}"
    real_id = resp.headers.get("Location", "").rsplit("/", 1)[-1]
    adapter._fixture_to_real_sprint[sid] = real_id
    if real_id not in adapter._created_sprints:
        adapter._created_sprints.append(real_id)


# ── When ──────────────────────────────────────────────────────────────

@when('the content library worker runs for cluster "{cluster}"')
def step_library_worker_run(context, cluster):
    step_library_provisioned(context, cluster)


@when('another logged-in user starts a sprint for cluster "{cluster}"')
def step_second_learner_starts(context, cluster):
    _login(context, OTHER_USER_ID)
    context.response = _post(context, f"/sprints/{cluster}/start", data={})
    assert context.response.status_code == 302
    context.second_sprint_url = context.response.headers.get("Location", "")


# ── Then: library shape ───────────────────────────────────────────────

@then('the library for cluster "{cluster}" has a lesson for every day 1-14')
def step_library_days_complete(context, cluster):
    from services.content_library import library_days
    days = library_days(get_live_adapter().sb, cluster)
    missing = [d for d in range(1, 15) if d not in days or not days[d]]
    assert not missing, f"library days missing/empty: {missing}"


@then('the library for cluster "{cluster}" has anatomy for all 3 projects')
def step_library_projects_complete(context, cluster):
    from services.content_library import library_projects
    projects = library_projects(get_live_adapter().sb, cluster)
    missing = [p for p in range(1, 4) if p not in projects]
    assert not missing, f"library projects missing: {missing}"


@then('the library for cluster "{cluster}" has day {day_no:d} titled "{title}"')
def step_library_day_titled(context, cluster, day_no, title):
    from services.content_library import library_days
    lesson = library_days(get_live_adapter().sb, cluster).get(day_no) or {}
    assert lesson.get("title") == title, \
        f"library day {day_no} title={lesson.get('title')!r}, expected {title!r}"


# ── Then: learner consumption (zero per-user LLM) ─────────────────────

@then('the response redirects to a sprint dashboard')
def step_redirect_a_sprint_dashboard(context):
    """"a sprint dashboard" variant — common_steps registers the "the" form."""
    import re as _re
    assert context.response.status_code in (301, 302, 303, 307, 308), \
        f"expected redirect, got {context.response.status_code}"
    loc = context.response.headers.get("Location", "")
    assert _re.search(r"/sprints/[0-9a-fA-F-]{36}$", loc), \
        f"expected redirect to a sprint dashboard, got Location {loc!r}"


def _assert_no_new_llm_calls(context):
    """The counting stub installed at provisioning time must show no NEW calls:
    learners consume the library — they never invoke the LLM chain."""
    counter = getattr(context, "library_llm_counter", None)
    baseline = getattr(context, "library_llm_baseline", None)
    assert counter is not None and baseline is not None, \
        "counting LLM stub not installed — run the provisioning step first"
    # Give a would-be fallback thread a moment to make its (forbidden) calls.
    time.sleep(0.2)
    assert counter["calls"] == baseline, \
        (f"learners triggered {counter['calls'] - baseline} per-user LLM calls, "
         f"expected 0 (library path must be LLM-free)")


@then('day 1 of the new sprint shows the library lesson with no per-user LLM call')
def step_new_sprint_day1_library(context):
    loc = context.response.headers.get("Location", "")
    assert "/sprints/" in loc, f"no sprint dashboard in redirect: {loc!r}"
    # The full library applied synchronously: every day already has its lesson.
    real_id = loc.rsplit("/", 1)[-1]
    import services.lesson_engine as le
    generated, total = le.generation_progress(get_live_adapter().sb, real_id)
    assert generated == total == 14, \
        f"library sprint not instantly provisioned: {generated}/{total}"
    _get(context, f"{loc}/day/1")
    html = _html(context)
    assert "Day lesson for Klaviyo flow setup for store" in html, \
        "day 1 does not render the library lesson"
    _assert_no_new_llm_calls(context)


@then('both sprints render the same day-4 lesson content')
def step_both_sprints_same_day4(context):
    first = getattr(context, "first_sprint_url")
    second = getattr(context, "second_sprint_url")
    assert first and second, "both learners must have started a sprint first"
    _get(context, f"{second}/day/4")
    second_html = _html(context)
    marker = "Day lesson for Klaviyo flow setup for store"
    assert marker in getattr(context, "first_day4_html", ""), \
        "first learner's day 4 does not render the library lesson"
    assert marker in second_html, \
        "second learner's day 4 does not render the same library lesson"


@then('the LLM was called zero times for either learner')
def step_llm_zero_for_learners(context):
    _assert_no_new_llm_calls(context)


@then("a new learner's day 7 shows the admin-edited title")
def step_new_learner_day7_edited(context):
    resp = _post(context, "/sprints/email-automation/start", data={})
    assert resp.status_code == 302
    loc = resp.headers.get("Location", "")
    _get(context, f"{loc}/day/7")
    html = _html(context)
    assert "Pricing your first contract" in html, \
        "day 7 does not render the admin-edited title"


# ── Then: fallback behaviour ──────────────────────────────────────────

@then("the sprint's generation status eventually reports lessons for every day")
def step_generation_status_ready(context):
    """Run the REAL per-sprint worker synchronously (stubbed LLM — exactly what
    the enrollment fallback thread runs) and verify the sprint fills."""
    import services.lesson_engine as le
    import services.video_engine as ve
    loc = context.response.headers.get("Location", "")
    real_id = loc.rsplit("/", 1)[-1]
    ve.voiceover_for_lesson = lambda *a, **k: None
    le.generate_sprint_content(get_live_adapter().sb, real_id)
    generated, total = le.generation_progress(get_live_adapter().sb, real_id)
    assert generated == total, f"generation incomplete: {generated}/{total}"


@then('the per-user LLM fallback was used exactly once for this sprint')
def step_fallback_used_once(context):
    """The library path was NOT used: the library stays empty and the sprint
    was filled by the per-sprint worker (the previous step ran it)."""
    from services.content_library import library_days
    days = library_days(get_live_adapter().sb, "ai-chatbots")
    assert not days, "library must remain empty on the fallback path"
    loc = context.response.headers.get("Location", "")
    real_id = loc.rsplit("/", 1)[-1]
    import services.lesson_engine as le
    generated, total = le.generation_progress(get_live_adapter().sb, real_id)
    assert generated == total, "fallback worker did not fill the sprint"


# ── Then: housekeeping ────────────────────────────────────────────────

@when('the sprint "{sid}" is deleted')
def step_sprint_deleted(context, sid):
    adapter = get_live_adapter()
    real_id = adapter.resolve_sprint_id(sid, resolve_only=True)
    adapter.sb.table("sprints").delete().eq("id", real_id).execute()


@then('the library for cluster "{cluster}" still has a lesson for every day 1-14')
def step_library_survives(context, cluster):
    step_library_days_complete(context, cluster)
