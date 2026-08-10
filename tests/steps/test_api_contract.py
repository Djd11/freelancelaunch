"""
Step Definitions: HTTP API Contract (tests/features/api-contract.feature)

Exercises the real Flask HTTP endpoints via the test client against an
in-memory FakeSupabase (see tests/support/fake_supabase.py). The fake is
installed by tests/environment.py when this feature runs.

Covers auth gating (401/302), request validation (400), and happy-path
response shapes for the v1 + Sprint Track JSON APIs.
"""
import json
import re
from behave import given, when, then

from tests.support.fake_supabase import FakeSupabase

TEST_USER_ID = "test-user-123"


# ─── helpers ──────────────────────────────────────────────────────────

def _reset(context):
    """Reset the in-memory DB between scenarios."""
    if not hasattr(context, "fake") or context.fake is None:
        context.fake = FakeSupabase()
        # install the patcher so routes/services see the fake
        from tests.environment import install_api_supabase
        install_api_supabase(context)
    context.fake.reset()
    context.response = None
    context.json_body = None


def _seed_user(context):
    context.fake.seed("user_profiles", [{
        "user_id": TEST_USER_ID,
        "avatar_url": "test@example.com",
        "display_name": "Test User",
        "cohort_id": None,
        "selected_topic_id": None,
    }])


def _login(context):
    with context.client.session_transaction() as sess:
        sess["user_id"] = TEST_USER_ID


def _logout(context):
    with context.client.session_transaction() as sess:
        sess.pop("user_id", None)


def _post(context, path, payload=None):
    kwargs = {}
    if payload is not None:
        kwargs["json"] = payload
    elif context.text is not None:
        kwargs["json"] = json.loads(context.text)
    context.response = context.client.post(path, **kwargs)


def _get(context, path):
    context.response = context.client.get(path)


# ─── GIVEN ────────────────────────────────────────────────────────────

@given("the app is running with an in-memory test database")
def step_inmem_db(context):
    _reset(context)


@given("a test user is logged in")
def step_logged_in(context):
    _seed_user(context)
    _login(context)


@given("I am not logged in")
def step_not_logged_in(context):
    _logout(context)


@given('a cohort video "{cv}" exists')
def step_cohort_video(context, cv):
    context.fake.seed("cohort_videos", [{"id": cv, "day_number": 1}])


@given('the platform "{platform}" is linked with status "{status}"')
def step_platform_status(context, platform, status):
    context.fake.seed("user_platforms", [{
        "user_id": TEST_USER_ID, "platform": platform, "status": status,
    }])


@given("a freelance pipeline row exists for the user")
def step_pipeline_row(context):
    context.fake.seed("freelance_pipeline", [{
        "user_id": TEST_USER_ID, "topic": "topic-id", "stage": "learning",
        "proposals_sent": 0, "contracts_won": 0, "total_earned": 0,
    }])


@given('an active sprint "{sid}" on day {n} for the test user')
def step_active_sprint(context, sid, n):
    context.fake.seed("sprints", [{
        "id": sid, "user_id": TEST_USER_ID, "cluster_key": "email-automation",
        "phase": "A", "current_day": int(n), "status": "active",
    }])
    context.fake.seed("sprint_days", [{
        "id": f"{sid}-d{n}", "sprint_id": sid, "day_no": int(n),
        "is_done": False, "phase": "A", "action_type": "setup", "title": "Day",
    }])
    # snapshot row so the meter delta path works
    context.fake.seed("sprint_unlock_snapshots", [{
        "sprint_id": sid, "user_id": TEST_USER_ID, "completed_days": int(n) - 1,
        "unlocked_count": 0, "total_in_cluster": 0, "last_delta": 0,
    }])


@given('a job cluster "{cluster}" with {n} active postings')
def step_job_cluster(context, cluster, n):
    context.fake.seed("job_clusters", [{
        "cluster_key": cluster, "job_count": int(n), "avg_rate": 200,
    }])
    for i in range(1, int(n) + 1):
        context.fake.seed("job_feed", [{
            "id": f"{cluster}-{i}", "cluster_key": cluster,
            "unlock_day": 1 if i % 14 == 1 else (i % 14) + 1,
            "status": "active", "rate": 100 + i, "experience_needed": "entry",
            "review_count": 0, "skills": ["code"], "title": f"Job {i}",
        }])


# ─── WHEN ─────────────────────────────────────────────────────────────

@when('I GET "{path}"')
def step_get(context, path):
    _get(context, path)


@when('I POST to "{path}" with JSON')
def step_post_json_doc(context, path):
    _post(context, path)


@when('I POST to "{path}" with JSON {body}')
def step_post_json_inline(context, path, body):
    _post(context, path, json.loads(body))


@when('I POST to "{path}"')
def step_post_no_body(context, path):
    _post(context, path)


# ─── THEN ─────────────────────────────────────────────────────────────

def _as_json(context):
    if context.json_body is None:
        context.json_body = context.response.get_json()
    return context.json_body


@then("the response status is {code}")
def step_status(context, code):
    assert context.response.status_code == int(code), (
        f"expected {code}, got {context.response.status_code}: "
        f"{context.response.get_data(as_text=True)[:300]}"
    )


@then('the JSON has error "{msg}"')
def step_json_error(context, msg):
    body = _as_json(context) or {}
    assert body.get("error") == msg, f"expected error {msg!r}, got {body!r}"


@then('the JSON has field "{field}" equal to {value}')
def step_json_field_eq(context, field, value):
    body = _as_json(context)
    assert field in body, f"field {field} missing from {body!r}"
    expected = _coerce(value)
    assert body[field] == expected, f"{field}: expected {expected!r}, got {body[field]!r}"


@then('the JSON has field "{field}" matching "{pattern}"')
def step_json_field_re(context, field, pattern):
    body = _as_json(context)
    assert field in body, f"field {field} missing from {body!r}"
    assert re.search(pattern, str(body[field])), f"{field}: {body[field]!r} !~ {pattern}"


@then('the JSON has field "{field}" as an integer')
def step_json_field_int(context, field):
    body = _as_json(context)
    assert field in body, f"field {field} missing from {body!r}"
    assert isinstance(body[field], int), f"{field}: expected int, got {type(body[field])}"


@then('the JSON has field "{field}" as an object')
def step_json_field_obj(context, field):
    body = _as_json(context)
    assert field in body, f"field {field} missing from {body!r}"
    assert isinstance(body[field], dict), f"{field}: expected object, got {type(body[field])}"


@then("the response body is a JSON array")
def step_json_array(context):
    assert isinstance(context.response.get_json(), list)


@then('the JSON path "{path}" is an integer')
def step_json_nested_int(context, path):
    body = _as_json(context)
    parts = path.split(".")
    cur = body
    for p in parts:
        assert isinstance(cur, dict) and p in cur, f"path {path!r} missing from {body!r}"
        cur = cur[p]
    assert isinstance(cur, int), f"{path}: expected int, got {type(cur)}"


def _coerce(value):
    """Coerce a feature-text literal ('true', '2', '/x', '"y"') to Python."""
    if value == "true":
        return True
    if value == "false":
        return False
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value
