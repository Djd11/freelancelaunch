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
