"""
Step Definitions: V2 Sprint Track — HTTP navigation & exhaustive API.

These run against the real Flask test client + in-memory FakeSupabase (installed
by environment.py for the "V2 Sprint Track Navigation" and "V2 Sprint Track API"
features). Unlike the service-level sprint tests, these assert the actual HTTP
surface: that every CTA renders a working link and that every /sprints/* route
is gated, validated, and returns the correct result.

All step texts here are intentionally unique vs. test_api_contract.py and
test_sprint_track.py so behave does not see duplicate definitions.
"""
import re
from behave import given, when, then

TEST_USER_ID = "test-user-123"
OTHER_USER_ID = "other-user-999"


# ─── helpers ──────────────────────────────────────────────────────────

def _get(context, path):
    context.response = context.client.get(path)
    context.page_html = context.response.get_data(as_text=True)
    return context.response


def _post(context, path, data=None):
    kwargs = {}
    if data is not None:
        kwargs["data"] = data
    context.response = context.client.post(path, **kwargs)
    context.page_html = context.response.get_data(as_text=True)
    return context.response


def _login(context):
    with context.client.session_transaction() as sess:
        sess["user_id"] = TEST_USER_ID


def _logout(context):
    with context.client.session_transaction() as sess:
        sess.pop("user_id", None)


def _reset(context):
    if not hasattr(context, "fake") or context.fake is None:
        from tests.environment import install_api_supabase
        context.fake = __import__("tests.support.fake_supabase", fromlist=["FakeSupabase"]).FakeSupabase()
        install_api_supabase(context)
    context.fake.reset()
    context.response = None
    context.page_html = ""
    context.created_sprint_id = None
    context.flash = []
    # clear accumulated session flash messages between scenarios (isolation)
    try:
        with context.client.session_transaction() as sess:
            sess.pop("_flashes", None)
    except Exception:
        pass


def _seed_std_user(context, cohort=True):
    profile = {
        "user_id": TEST_USER_ID,
        "avatar_url": "test@example.com",
        "display_name": "Test User",
        "cohort_id": "c1" if cohort else None,
        "selected_topic_id": "t1" if cohort else None,
    }
    context.fake.seed("user_profiles", [profile])
    if cohort:
        context.fake.seed("cohorts", [{
            "id": "c1", "topic_id": "t1", "current_day": 1, "max_days": 14, "name": "Test Cohort",
        }])
        context.fake.seed("topics", [{
            "id": "t1", "slug": "web-scraping", "name": "Web Scraping with Python",
        }])


_PHASE_DESC = {
    "A": "Skill Acquisition — rebuild real projects to build muscle memory.",
    "B": "Mock Contract — fulfill a real anonymized brief like it's paid.",
    "C": "Supply Chain — engineered proposals and the First-Bid challenge.",
}


def _day_action_payload(d):
    """Mirror sprint_planner.build_plan so day.html renders (action_payload)."""
    if d < 5:
        return {"project_index": max(d - 1, 0)}
    if d == 5:
        return {"detect": True}
    if 6 <= d <= 10:
        step = {"6": "brief", "7": "execute1", "8": "execute2", "9": "case-problem", "10": "case-result"}.get(str(d), "execute")
        return {"step": step}
    return {"step": "engineer" if d == 11 else ("first-bid" if d in (12, 13) else "iterate")}


def _seed_sprint(context, sid, days=14, day=1, user=TEST_USER_ID):
    context.fake.seed("sprints", [{
        "id": sid, "user_id": user, "cluster_key": "email-automation",
        "phase": "A", "current_day": day, "status": "active",
    }])
    phase_map = {d: "A" for d in range(1, 6)} | {d: "B" for d in range(6, 11)} | {d: "C" for d in range(11, 15)}
    for d in range(1, days + 1):
        phase = phase_map.get(d, "A")
        context.fake.seed("sprint_days", [{
            "id": f"{sid}-d{d}", "sprint_id": sid, "day_no": d, "is_done": False,
            "phase": phase,
            "action_type": "copywork" if d < 6 else ("contract" if d < 11 else "proposal"),
            "title": f"Day {d}",
            "description": _PHASE_DESC.get(phase, ""),
            "action_payload": _day_action_payload(d),
            "completed_at": None,
        }])
    context.fake.seed("sprint_unlock_snapshots", [{
        "sprint_id": sid, "user_id": user, "completed_days": day - 1,
        "unlocked_count": 0, "total_in_cluster": 0, "last_delta": 0,
    }])


def _location(context):
    return context.response.headers.get("Location", "")


def _html(context):
    """Return the last response body as text, whether _get/_post set page_html
    (test_sprint_http) or only context.response (test_api_contract)."""
    if getattr(context, "page_html", None) is not None:
        return context.page_html
    resp = getattr(context, "response", None)
    return resp.get_data(as_text=True) if resp is not None else ""


def _flash_text(context):
    msgs = []
    try:
        with context.client.session_transaction() as sess:
            for cat, txt in sess.get("_flashes", []):
                msgs.append(txt)
    except Exception:
        pass
    return " ".join(msgs)


# ══════════════════════════════════════════════════════════════════════
#  GIVEN
# ══════════════════════════════════════════════════════════════════════

@given("a logged-in user with an active cohort")
def step_logged_in_cohort(context):
    _reset(context)
    _seed_std_user(context, cohort=True)
    _login(context)


@given('I have an active sprint "{sid}" with {n} days')
def step_have_sprint(context, sid, n):
    _seed_sprint(context, sid, days=int(n))


@given('an active sprint "{sid}" on day {n} for another user')
def step_other_sprint(context, sid, n):
    _seed_sprint(context, sid, days=14, day=int(n), user=OTHER_USER_ID)


@given('a draft proposal "{pid}" exists for job "{jid}" on sprint "{sid}"')
def step_draft_proposal(context, pid, jid, sid):
    context.fake.seed("proposals", [{
        "id": pid, "sprint_id": sid, "user_id": TEST_USER_ID, "job_feed_id": jid,
        "status": "draft", "template_body": "I see you need X…", "hooks": ["I see you need X…"],
    }])


@given('the mock contract for sprint "{sid}" has passed verification')
def step_mock_passed(context, sid):
    """Seed a capstone brief + a passing verification_reviews row so badge_engine.issue can fire."""
    context.fake.seed("capstone_briefs", [{
        "id": f"{sid}-brief", "sprint_id": sid, "job_feed_id": f"email-automation-1",
        "title": "Client Brief · Seeded", "requirements": "Ship it",
        "constraints": {"deadline_days": 4, "budget": 180},
        "acceptance_criteria": ["done"], "verification_type": "auto",
        "submission_url": "https://example.com/deliverable",
    }])
    context.fake.seed("verification_reviews", [{
        "id": f"{sid}-rev", "capstone_brief_id": f"{sid}-brief",
        "user_id": TEST_USER_ID, "status": "pass",
        "feedback": "Automated acceptance checks passed. Phase C unlocked.",
    }])


# ══════════════════════════════════════════════════════════════════════
#  WHEN
# ══════════════════════════════════════════════════════════════════════

@when('I open "{path}"')
def step_open(context, path):
    _get(context, path)


@when("I open the authenticated dashboard")
def step_open_dashboard(context):
    _get(context, "/dashboard/")


@given("I am on the Sprint Track landing")
def step_on_landing(context):
    _get(context, "/sprints")


@when('I open the sprint dashboard for "{sid}"')
def step_open_sprint_dash(context, sid):
    _get(context, f"/sprints/{sid}")


@when('I click through to "{path}"')
def step_click_through(context, path):
    _get(context, path)


@when("I follow the redirect")
def step_follow_redirect(context):
    loc = _location(context)
    assert loc, "no redirect Location to follow"
    _get(context, loc)


@when('I start a sprint for cluster "{cluster}"')
def step_start_sprint(context, cluster):
    _post(context, "/sprints/new", data={"topic": cluster})
    loc = _location(context)
    m = re.search(r"/sprints/([^/]+)", loc or "")
    if m:
        context.created_sprint_id = m.group(1)


@when('I complete day {n} of sprint "{sid}"')
def step_complete_day(context, n, sid):
    _post(context, f"/sprints/{sid}/day/{n}/complete")


@when('I submit the start-sprint form to "{path}" for topic "{topic}"')
def step_post_form_topic(context, path, topic):
    _post(context, path, data={"topic": topic})
    # capture the created sprint id from the redirect so /sprints/{id} resolves
    loc = _location(context)
    m = re.search(r"/sprints/([^/]+)", loc or "")
    if m:
        context.created_sprint_id = m.group(1)


@when('I submit the contract form to "{path}" with submission_url "{url}"')
def step_post_form_submission(context, path, url):
    _post(context, path, data={"submission_url": url})


@when('I submit the contract form to "{path}" with no data')
def step_post_form_empty(context, path):
    _post(context, path)


# ══════════════════════════════════════════════════════════════════════
#  THEN — navigation / HTML assertions
# ══════════════════════════════════════════════════════════════════════

@then('the page contains a link to "{path}"')
def step_contains_link(context, path):
    body = _html(context)
    hrefs = sorted(set(re.findall(r'href="([^"]+)"', body)))
    status = getattr(context.response, "status_code", None)
    loc = _location(context)
    assert f'href="{path}"' in body, (
        f'expected href="{path}" in page; status={status} loc={loc!r} page hrefs: {hrefs}'
    )


@then('the link has text "{text}"')
def step_link_text(context, text):
    assert text in _html(context), f'expected text "{text}" in page'


@then('the page contains the text "{text}"')
def step_contains_text(context, text):
    assert text in _html(context), f'expected text "{text}" in page'


@then('the page contains a form posting to "{path}"')
def step_contains_form(context, path):
    body = _html(context)
    assert "form" in body, "no <form> in page"
    assert f'action="{path}"' in body, f'expected form action="{path}"'


@then('the form has a select named "{name}"')
def step_form_select(context, name):
    assert f'name="{name}"' in _html(context), f'expected <select name="{name}"> in page'


@then("the page is the Sprint Track landing")
def step_is_landing(context):
    body = _html(context)
    assert "Sprint Track" in body, "landing should say Sprint Track"
    assert "Start a new sprint" in body, "landing should show the start form"


@then('the page is the sprint dashboard for "{cluster}"')
def step_is_sprint_dash(context, cluster):
    body = _html(context)
    assert cluster.replace("-", " ").title() in body, f"dashboard should mention {cluster}"
    assert "Job Unlock Meter" in body, "dashboard should render the unlock meter"


@then("the page is the proposals page")
def step_is_proposals(context):
    body = _html(context)
    assert "First-Bid" in body or "Proposal" in body, "expected proposals page"


@then("each sprint-day CTA resolves to a 200 page")
def step_day_ctas_resolve(context):
    for d in range(1, 15):
        r = _get(context, f"/sprints/s1/day/{d}")
        assert r.status_code == 200, f"day {d} CTA returned {r.status_code}"


# ══════════════════════════════════════════════════════════════════════
#  THEN — redirects
# ══════════════════════════════════════════════════════════════════════

@then('the response redirects to "{path}"')
def step_redirects_to(context, path):
    loc = _location(context)
    if "{id}" in path and getattr(context, "created_sprint_id", None):
        path = path.format(id=context.created_sprint_id)
    assert loc == path, f"expected redirect to {path!r}, got {loc!r}"


# ══════════════════════════════════════════════════════════════════════
#  THEN — DB/state assertions (via FakeSupabase rows)
# ══════════════════════════════════════════════════════════════════════

@then('a job cluster "{cluster}" exists')
def step_cluster_exists(context, cluster):
    rows = context.fake.rows("job_clusters")
    assert any(r.get("cluster_key") == cluster for r in rows), f"cluster {cluster} missing: {rows}"


@then("the sprint has 14 planned days")
def step_sprint_14_days(context):
    sid = context.created_sprint_id
    days = context.fake.rows("sprint_days")
    mine = [d for d in days if d.get("sprint_id") == sid]
    assert len(mine) == 14, f"expected 14 sprint_days, got {len(mine)}"


@then("a sprint row exists for the logged-in user")
def step_sprint_owned(context):
    sprints = context.fake.rows("sprints")
    assert any(s.get("user_id") == TEST_USER_ID for s in sprints), f"no sprint for test user: {sprints}"


@then('the sprint "{sid}" is now on day {n}')
def step_sprint_day(context, sid, n):
    sprints = context.fake.rows("sprints")
    row = next((s for s in sprints if s.get("id") == sid), None)
    assert row, f"sprint {sid} missing"
    assert row.get("current_day") == int(n), f"expected current_day {n}, got {row.get('current_day')}"


@then('day {n} of sprint "{sid}" is marked done')
def step_day_done(context, n, sid):
    days = context.fake.rows("sprint_days")
    row = next((d for d in days if d.get("sprint_id") == sid and d.get("day_no") == int(n)), None)
    assert row, f"day {n} of {sid} missing"
    assert row.get("is_done") is True, f"day {n} not marked done: {row}"


@then('the flash message mentions "{text}"')
def step_flash_mentions(context, text):
    assert text.lower() in _flash_text(context).lower(), f'flash did not mention "{text}": {_flash_text(context)!r}'


@then('a verification review is recorded for sprint "{sid}"')
def step_verification_recorded(context, sid):
    reviews = context.fake.rows("verification_reviews")
    assert reviews, f"no verification_reviews recorded: {reviews}"


@then('the proposal "{pid}" is marked submitted')
def step_proposal_submitted(context, pid):
    props = context.fake.rows("proposals")
    row = next((p for p in props if p.get("id") == pid), None)
    assert row, f"proposal {pid} missing"
    assert row.get("status") == "submitted", f"proposal {pid} status={row.get('status')}"


@then("the page is the contract page")
def step_is_contract(context):
    body = _html(context)
    assert "Mock Contract" in body or "Client Brief" in body or "Your First" in body, (
        f"expected contract page, got: {body[:200]!r}"
    )


@then("the page is the badge page")
def step_is_badge(context):
    body = _html(context)
    assert "Badge" in body or "badge" in body, f"expected badge page, got: {body[:200]!r}"


@then("every rendered href resolves to a live page")
def step_every_href_live(context):
    """Walk every internal href on the last response and assert it is not a dead end.

    A live page means: status 200, or a 3xx redirect whose Location is also
    reachable (so /dashboard → /dashboard/ still counts as live). External
    absolute URLs, anchors, mailto, and javascript: are ignored.
    """
    body = _html(context)
    hrefs = sorted(set(re.findall(r'href="([^"]+)"', body)))
    dead = []
    for href in hrefs:
        if not href or href.startswith(("#", "mailto:", "javascript:", "data:", "http://", "https://")):
            continue
        # strip query/fragment for the probe
        path = href.split("?", 1)[0].split("#", 1)[0]
        if not path.startswith("/"):
            continue
        r = context.client.get(path)
        if r.status_code == 200:
            continue
        if 300 <= r.status_code < 400:
            loc = r.headers.get("Location", "")
            # follow one hop
            if loc:
                r2 = context.client.get(loc)
                if r2.status_code in (200, 302, 303, 307, 308):
                    continue
        dead.append(f"{href} → {r.status_code}")
    assert not dead, f"dead CTAs on page: {dead}"


@then('the created sprint is in phase "{phase}"')
def step_created_phase(context, phase):
    sid = getattr(context, "created_sprint_id", None)
    assert sid, "no created_sprint_id — did the create step run?"
    sprints = context.fake.rows("sprints")
    row = next((s for s in sprints if s.get("id") == sid), None)
    assert row, f"created sprint {sid} missing"
    assert row.get("phase") == phase, f"expected phase {phase}, got {row.get('phase')}"


@then("the created sprint is on day {n}")
def step_created_day(context, n):
    sid = getattr(context, "created_sprint_id", None)
    assert sid, "no created_sprint_id"
    sprints = context.fake.rows("sprints")
    row = next((s for s in sprints if s.get("id") == sid), None)
    assert row, f"created sprint {sid} missing"
    assert row.get("current_day") == int(n), f"expected day {n}, got {row.get('current_day')}"


@then("an unlock snapshot exists for the created sprint")
def step_unlock_snapshot(context):
    sid = getattr(context, "created_sprint_id", None)
    assert sid, "no created_sprint_id"
    snaps = context.fake.rows("sprint_unlock_snapshots")
    assert any(s.get("sprint_id") == sid for s in snaps), f"no unlock snapshot for {sid}: {snaps}"


@then('the sprint "{sid}" is in phase "{phase}"')
def step_sprint_phase(context, sid, phase):
    sprints = context.fake.rows("sprints")
    row = next((s for s in sprints if s.get("id") == sid), None)
    assert row, f"sprint {sid} missing"
    assert row.get("phase") == phase, f"expected phase {phase}, got {row.get('phase')}"


@then('a capstone brief exists for sprint "{sid}"')
def step_brief_exists(context, sid):
    briefs = context.fake.rows("capstone_briefs")
    assert any(b.get("sprint_id") == sid for b in briefs), f"no capstone brief for {sid}: {briefs}"


@then('draft proposals exist for sprint "{sid}"')
def step_drafts_exist(context, sid):
    props = context.fake.rows("proposals")
    mine = [p for p in props if p.get("sprint_id") == sid]
    assert mine, f"no draft proposals for {sid}"


@then('no badge is issued for sprint "{sid}"')
def step_no_badge(context, sid):
    badges = context.fake.rows("badges")
    mine = [b for b in badges if b.get("sprint_id") == sid]
    assert not mine, f"unexpected badge issued for {sid}: {mine}"


@then('a badge is issued for sprint "{sid}"')
def step_badge_issued(context, sid):
    badges = context.fake.rows("badges")
    mine = [b for b in badges if b.get("sprint_id") == sid]
    assert mine, f"no badge issued for {sid}: {badges}"
