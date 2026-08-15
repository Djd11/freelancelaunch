"""Common BDD steps — HTTP surface + page/text/JSON assertions (shared by all 8 features).

Works with LiveDBAdapter: fake IDs are resolved to real Supabase UUIDs at runtime.
"""
import re
import json as _json
from behave import given, when, then

from tests.live_db_adapter import get_live_adapter, TEST_USER_ID, OTHER_USER_ID, ADMIN_USER_ID

# The adapter resolves these at runtime
def _resolve_user_id(context, fake_id=TEST_USER_ID):
    return get_live_adapter().resolve_user_id(fake_id)

def _resolve_sprint_id(context, fake_id, cluster="email-automation", user_fake=TEST_USER_ID):
    return get_live_adapter().resolve_sprint_id(fake_id, cluster, user_fake)


def _get(context, path):
    context.response = context.client.get(path)
    context.page_html = context.response.get_data(as_text=True)
    return context.response


def _post(context, path, data=None, json=None):
    kwargs = {}
    if json is not None:
        kwargs["json"] = json
    elif data is not None:
        kwargs["data"] = data
    context.response = context.client.post(path, **kwargs)
    context.page_html = context.response.get_data(as_text=True)
    context.last_json = context.response.get_json(silent=True)
    return context.response


def _login(context, user_id=TEST_USER_ID):
    real_id = _resolve_user_id(context, user_id)
    with context.client.session_transaction() as sess:
        sess["user_id"] = real_id


def _login_with_name(context, display_name, user_id=TEST_USER_ID):
    adapter = get_live_adapter()
    real_id = adapter.resolve_user_id(user_id)
    # Ensure user_profiles row exists with display_name
    adapter.sb.table("user_profiles").upsert({
        "user_id": real_id,
        "display_name": display_name,
        "headline": "Freelancer · Email Automation & Web Scraping",
        "is_public": True,
    }, on_conflict="user_id").execute()
    _login(context, user_id)


def _location(context):
    return context.response.headers.get("Location", "")


def _html(context):
    return getattr(context, "page_html", "") or (
        context.response.get_data(as_text=True) if context.response is not None else ""
    )


# ── Givens: environment ────────────────────────────────────────────
@given('the app is running with an in-memory test database')
def step_running(context):
    pass  # environment.before_scenario already set up LiveDBAdapter


@given('a logged-in user')
def step_logged_in(context):
    _login(context)


@given('a logged-in user with display name "{name}"')
def step_logged_in_name(context, name):
    _login_with_name(context, name)


@given('I am not logged in')
def step_not_logged_in(context):
    with context.client.session_transaction() as sess:
        sess.pop("user_id", None)


@given('I am logged in as an admin user')
def step_admin_login(context):
    _login(context, ADMIN_USER_ID)


# ── When: HTTP surface ─────────────────────────────────────────────
@when('I GET "{path}"')
def step_get(context, path):
    _get(context, path)


@when('I POST to "{path}" with JSON {payload}')
def step_post_json(context, path, payload):
    data = _json.loads(payload)
    _post(context, path, json=data)
    # Admin create endpoints return 201 JSON → track the created row so
    # after_scenario cleanup removes it (no leaked rows across runs).
    admin_create_tables = {
        "/admin/clusters/create": "job_clusters",
        "/admin/feed/create": "job_feed",
        "/admin/cohorts/create": "cohorts",
    }
    table = admin_create_tables.get(path)
    if table and context.last_json and context.response.status_code == 201:
        get_live_adapter().track_created(table, context.last_json.get("id"))


# ── Then: HTTP assertions ──────────────────────────────────────────
@then('the response status is {n}')
def step_status(context, n):
    assert context.response.status_code == int(n), \
        f"expected {n}, got {context.response.status_code}"


@then('the response redirects to "{path}"')
def step_redirect(context, path):
    assert context.response.status_code in (301, 302, 303, 307, 308), \
        f"expected redirect, got {context.response.status_code}"
    loc = _location(context)
    assert loc == path, f"expected Location {path}, got {loc}"


@then('the page contains the text "{text}"')
def step_contains(context, text):
    assert text in _html(context), f"page missing text: {text!r}"


@then('the page does not contain the text "{text}"')
def step_not_contains(context, text):
    assert text not in _html(context), f"page unexpectedly contains: {text!r}"


@then('the page contains a link to "{path}"')
def step_contains_link(context, path):
    html = _html(context)
    assert f'href="{path}"' in html or f'href="{path}/"' in html, \
        f"page missing link to {path!r}"


@then('the page contains a link to start a sprint for "{key}"')
def step_contains_start_link(context, key):
    assert f'/sprints/{key}/start' in _html(context), f"missing start link for {key}"


@then('the flash message mentions "{text}"')
def step_flash(context, text):
    with context.client.session_transaction() as sess:
        flashes = " ".join(txt for cat, txt in sess.get("_flashes", []))
    assert text in flashes, f"flash missing {text!r}: {flashes!r}"


@then('the page contains a lock indicator on Phase B')
def step_lock_b(context):
    assert "Unlocks when Phase A passes verification" in _html(context), "Phase B lock missing"


@then('the page contains a lock indicator on Phase C')
def step_lock_c(context):
    assert "Locked until Mock Contract passes" in _html(context), "Phase C lock missing"


@then('Phase B is not locked')
def step_b_not_locked(context):
    assert "Unlocks when Phase A passes verification" not in _html(context), "Phase B still locked"


# ── Then: JSON assertions ──────────────────────────────────────────
@then('the JSON has field "{field}" equal to true')
def step_json_true(context, field):
    assert context.last_json is not None, "no JSON response"
    assert context.last_json.get(field) is True, f"{field} != true"


@then('the JSON has field "{field}" present')
def step_json_present(context, field):
    assert context.last_json is not None, "no JSON response"
    assert field in context.last_json, f"missing JSON field {field}"


@then('the JSON has field "{field}" containing "{text}"')
def step_json_containing(context, field, text):
    assert context.last_json is not None, "no JSON response"
    assert text in str(context.last_json.get(field, "")), f"{field} missing {text!r}"


@then('the JSON has field "{field}" not containing "{text}"')
def step_json_not_containing(context, field, text):
    assert context.last_json is not None, "no JSON response"
    assert text not in str(context.last_json.get(field, "")), f"{field} unexpectedly has {text!r}"


@then('the JSON path "{path}" is an integer')
def step_json_path_int(context, path):
    assert context.last_json is not None, "no JSON response"
    parts = path.split(".")
    value = context.last_json
    for p in parts:
        value = value[p]
    assert isinstance(value, int), f"{path} = {value!r}, not an int"


@then('the JSON has field "{field}" equal to "{value}"')
def step_json_field_equals(context, field, value):
    assert context.last_json is not None, "no JSON response"
    actual = context.last_json.get(field)
    assert actual == value, f"expected {field}={value!r}, got {actual!r}"


@then('the JSON has field "{field}" equal to {value:d}')
def step_json_field_equals_int(context, field, value):
    assert context.last_json is not None, "no JSON response"
    actual = context.last_json.get(field)
    assert actual == value, f"expected {field}={value}, got {actual!r}"