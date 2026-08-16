"""UI/UX steps — CTA walkthrough helpers (ui-ux.feature, api.feature).

Adds the small number of assertions the HTTP surface steps don't cover:
enrollment redirect capture (the created sprint UUID), element-attribute
presence, and dead-link detection (href="#").
"""
import re

from behave import when, then

from tests.steps.common_steps import _get, _post

_UUID_RE = r"[0-9a-fA-F-]{36}"


@when('I POST to the start-sprint form for cluster "{cluster}"')
def step_ui_start_sprint(context, cluster):
    resp = _post(context, f"/sprints/{cluster}/start", data={})
    assert resp.status_code == 302, f"start returned {resp.status_code}, expected 302"
    loc = resp.headers.get("Location", "")
    m = re.search(rf"/sprints/({_UUID_RE})$", loc)
    assert m, f"no sprint UUID in start redirect Location: {loc!r}"
    context.sprint_url = f"/sprints/{m.group(1)}"


@then('I can open the created sprint dashboard')
def step_ui_open_sprint(context):
    url = getattr(context, "sprint_url", None)
    assert url, "no sprint URL captured — run the start-sprint step first"
    resp = _get(context, url)
    assert resp.status_code == 200, f"dashboard returned {resp.status_code}"


@then('the page contains an element with attribute "{attr}"')
def step_ui_has_attribute(context, attr):
    html = getattr(context, "page_html", "") or (
        context.response.get_data(as_text=True) if context.response is not None else ""
    )
    assert f"{attr}=" in html, f"page has no element with attribute {attr!r}"


@then('the page does not contain any dead link')
def step_ui_no_dead_links(context):
    html = getattr(context, "page_html", "") or (
        context.response.get_data(as_text=True) if context.response is not None else ""
    )
    assert 'href="#"' not in html, 'page contains a dead link href="#"'


@then('the page contains an element with id "{eid}"')
def step_ui_has_id(context, eid):
    html = getattr(context, "page_html", "") or (
        context.response.get_data(as_text=True) if context.response is not None else ""
    )
    assert f'id="{eid}"' in html, f"page has no element with id {eid!r}"


@then('the page contains an element with name "{name}"')
def step_ui_has_name(context, name):
    html = getattr(context, "page_html", "") or (
        context.response.get_data(as_text=True) if context.response is not None else ""
    )
    assert f'name="{name}"' in html, f"page has no element with name {name!r}"


@then('the page contains an element with class "{cls}"')
def step_ui_has_class(context, cls):
    html = getattr(context, "page_html", "") or (
        context.response.get_data(as_text=True) if context.response is not None else ""
    )
    assert f'class="' in html and f"{cls}" in html, f"page has no element with class {cls!r}"


@then('the page contains a link to the anchor "{anchor}"')
def step_ui_has_anchor_link(context, anchor):
    html = getattr(context, "page_html", "") or (
        context.response.get_data(as_text=True) if context.response is not None else ""
    )
    assert f'href="#{anchor}"' in html, f"page missing link to #{anchor}"


@when('I submit the form at "{path}" with data {payload}')
def step_ui_post_form_json(context, path, payload):
    """POST an HTML form (urlencoded, not JSON) — exercises the browser form
    path of a route that also accepts JSON.

    Admin create routes answer the HTML form path with a 302 redirect (not
    the 201 JSON the JSON step relies on), so the created row must be resolved
    and tracked here — otherwise it leaks past after_scenario cleanup and
    corrupts later order-dependent lookups (e.g. the mentor/lesson engine's
    "first job by unlock_day" pick).
    """
    import json as _json
    from tests.live_db_adapter import get_live_adapter
    data = _json.loads(payload)
    _post(context, path, data=data)
    # path -> (table, identifying field the form payload carries)
    admin_create = {
        "/admin/clusters/create": ("job_clusters", "cluster_key"),
        "/admin/cohorts/create": ("cohorts", "name"),
        "/admin/feed/create": ("job_feed", "title"),
    }
    entry = admin_create.get(path)
    if not entry or context.response.status_code not in (301, 302, 303, 307, 308):
        return
    table, lookup_field = entry
    lookup_value = data.get(lookup_field)
    if not lookup_value:
        return
    rows = get_live_adapter().sb.table(table).select("id") \
        .eq(lookup_field, lookup_value).limit(5).execute().data
    for row in rows:
        get_live_adapter().track_created(table, row.get("id"))
