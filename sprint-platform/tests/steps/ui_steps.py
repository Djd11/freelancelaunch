"""UI/UX steps — CTA walkthrough helpers (ui-ux.feature, api.feature).

Adds the small number of assertions the HTTP surface steps don't cover:
enrollment redirect capture (the created sprint UUID), element-attribute
presence, and dead-link detection (href="#").
"""
import re

from behave import when, then

from tests.steps.common_steps import _get, _post, _html

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


@then('the pre-quiz appears before the lesson player')
def step_ui_prequiz_before_player(context):
    """The pre-quiz engagement block must render ABOVE the TwoPanel lesson player
    in document order — for BOTH the voiceover variant (data-lesson-player) and
    the non-voiceover variant (the 'TwoPanel' subtitle text)."""
    html = getattr(context, "page_html", "") or (
        context.response.get_data(as_text=True) if context.response is not None else ""
    )
    pq = html.find("Before you watch")
    assert pq != -1, "pre-quiz block (Before you watch) not found on the page"
    player = html.find("data-lesson-player")
    two_panel = html.find("TwoPanel")
    marker = player if player != -1 else two_panel
    assert marker != -1, "no lesson player marker found on the page"
    assert pq < marker, "pre-quiz does not appear before the lesson player"


@then('the page does not contain any dead link')
def step_ui_no_dead_links(context):
    html = getattr(context, "page_html", "") or (
        context.response.get_data(as_text=True) if context.response is not None else ""
    )
    assert 'href="#"' not in html, 'page contains a dead link href="#"'


@then('the lesson content is readable on the page outside the player JSON')
def step_ui_lesson_readable(context):
    """The lesson's script + key points must be server-rendered as readable
    text on the day view — a voiceover lesson previously rendered ONLY the JS
    player, whose kinetic text reveals a word or two at a time, so the learner
    found no meaningful content without playing the whole video.

    The player's data lives in window.__LESSON_PROPS__ inside <script> tags —
    strip them so this asserts real rendered content, not the JSON blob."""
    html = getattr(context, "page_html", "") or (
        context.response.get_data(as_text=True) if context.response is not None else ""
    )
    stripped = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL)
    assert "data-lesson-content" in stripped, "no readable lesson block on the day view"
    assert "What the posting literally asks for" in stripped, \
        "key points not rendered as readable text"
    assert "Today you rebuild the smallest real version" in stripped, \
        "lesson script not rendered as readable text"


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


@then('the page does not contain an element with class "{cls}"')
def step_ui_not_has_class(context, cls):
    """Negative class check — e.g. a draft case study check-item must NOT
    carry the 'done' class (profile.html renders it only when not is_draft)."""
    html = getattr(context, "page_html", "") or (
        context.response.get_data(as_text=True) if context.response is not None else ""
    )
    assert f"{cls}" not in html, f"page unexpectedly has element with class {cls!r}"

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


# ── Then: check-item state (scoped to the labelled item, not page-wide) ─────
def _check_item_state(html, label, cls):
    """True when the .check-item that wraps <b>{label}</b> carries the {cls} class.

    The check-item markup is `<div class="check-item[ done] ...><div class="cbox">…
    </div><div><b>LABEL</b>…` — find the label, walk back to the nearest preceding
    `class="check-item…"` within a sane window, and read its token set."""
    needle = '<b>{}</b>'.format(label)
    idx = html.find(needle)
    if idx == -1:
        idx = html.find(label)
    if idx == -1:
        return False
    ci = html.rfind('class="check-item', 0, idx)
    if ci == -1 or idx - ci > 800:
        return False
    q = html.find('"', ci + len('class="'))
    if q == -1:
        return False
    return cls in html[ci:q].split()


@then('the check-item "{label}" is marked done')
def step_check_item_done(context, label):
    assert _check_item_state(_html(context), label, "done"), \
        f'check-item "{label}" is not marked done'


@then('the check-item "{label}" is not marked done')
def step_check_item_not_done(context, label):
    assert not _check_item_state(_html(context), label, "done"), \
        f'check-item "{label}" is unexpectedly marked done'


# ── Then: rubric auto-check checkboxes (fix #7) ────────────────────────────
@then('the page contains at least {n:d} rubric checkboxes')
def step_at_least_n_checkboxes(context, n):
    total = _html(context).count('type="checkbox"')
    assert total >= n, f"expected at least {n} rubric checkboxes, got {total}"


@then('the rubric checkboxes are all checked')
def step_checkboxes_all_checked(context):
    html = _html(context)
    total = html.count('type="checkbox"')
    assert total > 0, "no rubric checkboxes found"
    checked = len(re.findall(r'type="checkbox"[^>]*\bchecked', html))
    assert checked == total, f"expected all {total} checkboxes checked, only {checked} are"


@then('the rubric checkboxes are not checked')
def step_checkboxes_none_checked(context):
    html = _html(context)
    total = html.count('type="checkbox"')
    assert total > 0, "no rubric checkboxes found"
    checked = len(re.findall(r'type="checkbox"[^>]*\bchecked', html))
    assert checked == 0, f"expected 0 checked checkboxes, got {checked}"


@then('the rubric checkboxes are not disabled')
def step_checkboxes_not_disabled(context):
    html = _html(context)
    # Find all checkboxes and verify none have 'disabled' attribute
    checkboxes = re.findall(r'<input[^>]*type="checkbox"[^>]*>', html)
    assert checkboxes, "no rubric checkboxes found"
    for cb in checkboxes:
        assert 'disabled' not in cb, f"found disabled checkbox: {cb}"


@then('the page contains a check-item "{label}"')
def step_page_has_checkitem(context, label):
    html = _html(context)
    assert f'<b>{label}</b>' in html, f'page has no check-item with label {label!r}'
    # Also verify it's within a check-item div
    ci = html.rfind('class="check-item', 0, html.find(label))
    assert ci != -1, f'label {label!r} not inside a check-item div'


@then('the first rubric checkbox is checked')
def step_first_checkbox_checked(context):
    html = _html(context)
    # Find the first checkbox (type="checkbox") and verify it has 'checked'
    checkboxes = re.findall(r'<input[^>]*type="checkbox"[^>]*>', html)
    assert checkboxes, "no rubric checkboxes found"
    assert 'checked' in checkboxes[0], f"first checkbox not checked: {checkboxes[0]}"


@then('the second rubric checkbox is checked')
def step_second_checkbox_checked(context):
    html = _html(context)
    checkboxes = re.findall(r'<input[^>]*type="checkbox"[^>]*>', html)
    assert len(checkboxes) >= 2, f"expected at least 2 checkboxes, got {len(checkboxes)}"
    assert 'checked' in checkboxes[1], f"second checkbox not checked: {checkboxes[1]}"


@then('the third rubric checkbox is not checked')
def step_third_checkbox_not_checked(context):
    html = _html(context)
    checkboxes = re.findall(r'<input[^>]*type="checkbox"[^>]*>', html)
    assert len(checkboxes) >= 3, f"expected at least 3 checkboxes, got {len(checkboxes)}"
    assert 'checked' not in checkboxes[2], f"third checkbox unexpectedly checked: {checkboxes[2]}"
