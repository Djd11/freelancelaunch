"""
Step Definitions: Dashboard Course Stats — BDD for features/dashboard-course-stats.feature

Captures the three core course statistics off the rendered dashboard —
  1. HOW MANY courses   → count of tabs in the "YOUR COURSES" strip
  2. WHAT the progress  → per-tab "done/total" fraction, active-course
                         "days completed" label, and progress-bar width %
  3. WHERE the learner is → "Day N of M" current position

Browser management mirrors tests/steps/test_page_audit.py: the Playwright
browser lives on underscore-prefixed attrs so it survives behave's per-scenario
layer pops; a fresh page is created per scenario via environment.py.
"""
import re

from behave import given, when, then, step, use_step_matcher

# Parse matcher (default) — restore explicitly so this file is self-documenting.
use_step_matcher("parse")


# ─── Browser helpers (underscore attrs → survive scenario layer pops) ────────


def _browser(context):
    if getattr(context, "_pw_browser", None) is None:
        from playwright.sync_api import sync_playwright
        context._pw_playwright = sync_playwright().start()
        try:
            context._pw_browser = context._pw_playwright.chromium.launch(
                channel="chrome", headless=False, slow_mo=30,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
        except Exception:
            context._pw_browser = context._pw_playwright.chromium.launch(
                headless=False, slow_mo=30,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
    return context._pw_browser


def _page(context):
    if context.page is None:
        browser = _browser(context)
        context.page = browser.new_page(viewport={"width": 1366, "height": 900})
        context.page.set_default_timeout(15000)
        context.console_errors = []
        context.page.on("console", lambda m: context.console_errors.append(f"[{m.type}] {m.text}")
                        if m.type == "error" else None)
        context.page.on("pageerror", lambda e: context.console_errors.append(f"[pageerror] {e}"))
    return context.page


# ─── Capture: read the rendered stats into context.course_stats ─────────────


# Registered with @step (not @when) so "And/Then I capture ..." also matches —
# in CS-1 the capture step follows a Then, which Gherkin treats as a Then step.
@step("I capture the course stats from the dashboard")
def step_capture_course_stats(context):
    page = _page(context)
    body = page.inner_text("body")

    # 1) HOW MANY courses → tabs inside the horizontal "YOUR COURSES" strip.
    tab_loc = page.locator("div.overflow-x-auto a")
    tab_texts = [t.inner_text().strip() for t in tab_loc.all() if t.inner_text().strip()]
    course_count = len(tab_texts)

    # 2) Per-tab progress fraction: each tab ends with "N/M".
    tab_fractions = []
    for txt in tab_texts:
        m = re.search(r"(\d+)/(\d+)\s*$", txt)
        tab_fractions.append((int(m.group(1)), int(m.group(2))) if m else None)

    # 3) Active course position: "Day N of M · X/Y days completed".
    pos = re.search(r"Day\s+(\d+)\s+of\s+(\d+)", body)
    frac = re.search(r"(\d+)/(\d+)\s+days\s+completed", body)

    # 4) Active course progress bar width (%). The active stage card's bar is
    #    the only div.gradient-primary carrying an inline width on this page.
    width_pct = None
    bar = page.locator("div.gradient-primary").first
    if bar.count() > 0:
        style = bar.get_attribute("style") or ""
        m = re.search(r"width:\s*([\d.]+)%", style)
        width_pct = float(m.group(1)) if m else None

    context.course_stats = {
        "course_count": course_count,
        "tab_texts": tab_texts,
        "tab_fractions": tab_fractions,
        "current_day": int(pos.group(1)) if pos else None,
        "max_days": int(pos.group(2)) if pos else None,
        "progress_fraction": (int(frac.group(1)), int(frac.group(2))) if frac else None,
        "progress_bar_pct": width_pct,
    }


# ─── Then: verify the captured stats ─────────────────────────────────────────


@then('I should see the "YOUR COURSES" heading')
def step_see_courses_heading(context):
    page = _page(context)
    body = page.inner_text("body")
    assert "YOUR COURSES" in body, "'YOUR COURSES' heading not found on dashboard"


@then("the captured course count should be at least {count:d}")
def step_captured_count_at_least(context, count):
    stats = context.course_stats
    assert stats["course_count"] >= count, \
        f"expected >= {count} courses, captured {stats['course_count']}"


@then("the captured course count should match the number of course tabs rendered")
def step_captured_count_matches_tabs(context):
    page = _page(context)
    rendered = page.locator("div.overflow-x-auto a").count()
    assert context.course_stats["course_count"] == rendered, \
        f"captured count {context.course_stats['course_count']} != rendered tabs {rendered}"


@then('every captured course tab should show a progress fraction "done/total"')
def step_every_tab_shows_fraction(context):
    stats = context.course_stats
    assert stats["tab_fractions"], "no course tabs captured"
    for text, frac in zip(stats["tab_texts"], stats["tab_fractions"]):
        assert frac is not None, f"course tab missing 'done/total' fraction: {text!r}"
        done, total = frac
        assert total > 0, f"course tab total must be > 0: {text!r}"
        assert 0 <= done <= total, f"course tab fraction out of range {done}/{total}: {text!r}"


@then('the captured active course should show a "days completed" label')
def step_captured_days_completed_label(context):
    frac = context.course_stats["progress_fraction"]
    assert frac is not None, "active course 'days completed' label (X/Y) not found"


@then("the captured active course progress bar should be a valid percentage between 0% and 100%")
def step_captured_bar_valid(context):
    pct = context.course_stats["progress_bar_pct"]
    assert pct is not None, "active course progress bar width (%) not found"
    assert 0 <= pct <= 100, f"progress bar width {pct}% out of range 0..100"


@then('the captured current position should read "Day N of M"')
def step_captured_position_format(context):
    stats = context.course_stats
    assert stats["current_day"] is not None and stats["max_days"] is not None, \
        "'Day N of M' current position not found on dashboard"


@then("the captured current day N should be between 1 and M")
def step_captured_day_in_range(context):
    stats = context.course_stats
    day, max_days = stats["current_day"], stats["max_days"]
    assert max_days and 1 <= day <= max_days, \
        f"current day {day} not within 1..{max_days}"


@then("the captured progress fraction total should match the position total M")
def step_captured_fraction_total_matches(context):
    stats = context.course_stats
    frac = stats["progress_fraction"]
    assert frac is not None, "progress fraction not captured"
    assert frac[1] == stats["max_days"], \
        f"progress total {frac[1]} != position total {stats['max_days']}"
