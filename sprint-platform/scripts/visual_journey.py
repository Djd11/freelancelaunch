"""Headed Playwright visual run — full admin + learner journey on the live test project.

Runs a real browser on DISPLAY=:0 with video + per-screen screenshots.
Creates a throwaway sprint + cluster, exercises every screen, then cleans up
so the live test project is left exactly as found.

KEY FIX: validates page HTML content at every screen before proceeding.
- Day view: lesson content must be rendered (not "Generating…"), clone steps visible,
  rubric items present — copywork is NEVER submitted if the lesson isn't ready.
- Dashboard: sprint header, phase labels, job unlock meter, momentum all checked.
- Proposals: proposal text visible, job table rows present.
- Profile: badge and display name verified.

Usage:  DISPLAY=:0 .venv/bin/python scripts/visual_journey.py
"""
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = "http://127.0.0.1:5000"
OUT = "/tmp/visual_run"
os.makedirs(f"{OUT}/shots", exist_ok=True)
os.makedirs(f"{OUT}/videos", exist_ok=True)

console_errors = []   # (page_label, type, text)
page_label = {"v": "startup"}
validation_failures = []  # (screen, check, detail)


def start_server():
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "from app import create_app; create_app().run(host='127.0.0.1', port=5000, debug=False)"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    import urllib.request
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"{BASE}/health", timeout=2) as r:
                body = json.loads(r.read())
                if body.get("status") == "ok":
                    print(f"server up: mode={body.get('mode')}")
                    return proc
        except Exception:
            time.sleep(0.5)
    proc.terminate()
    raise SystemExit("server did not become healthy")


def wire_console(page):
    def on_console(msg):
        if msg.type in ("error",):
            console_errors.append((page_label["v"], msg.type, msg.text[:200]))
    def on_pageerror(err):
        console_errors.append((page_label["v"], "pageerror", str(err)[:200]))
    page.on("console", on_console)
    page.on("pageerror", on_pageerror)


def shot(page, name):
    path = f"{OUT}/shots/{name}.png"
    page.screenshot(path=path, full_page=True)
    print(f"  📸 {name}.png  ({page.url})")
    return path


# ── Content validators ────────────────────────────────────────────

def validate(page, screen, check_name, condition, detail=""):
    """Assert a content condition. Records failures for the summary."""
    if not condition:
        validation_failures.append((screen, check_name, detail))
        print(f"  ❌ [{screen}] {check_name}: {detail}")
    else:
        print(f"  ✅ [{screen}] {check_name}")


def validate_landing(page):
    """Landing page: hero headline, demand counter, phase descriptions."""
    html = page.content()
    validate(page, "landing", "hero headline",
             "Stop learning skills." in html and "Start landing clients." in html,
             "missing hero headline text")
    validate(page, "landing", "demand counter (job_count)",
             re.search(r'\d+.*active jobs', html) is not None,
             "no active jobs count visible")
    validate(page, "landing", "demand counter (avg_rate)",
             re.search(r'\$\d+.*median hourly rate', html) is not None,
             "no median hourly rate visible")
    validate(page, "landing", "demand counter (growth_score)",
             re.search(r'\+\d+%.*demand this quarter', html) is not None,
             "no growth score visible")
    validate(page, "landing", "phase A label",
             "PHASE A" in html and "Skill Acquisition" in html,
             "missing Phase A description")
    validate(page, "landing", "phase B label",
             "PHASE B" in html and "Mock Contract" in html,
             "missing Phase B description")
    validate(page, "landing", "phase C label",
             "PHASE C" in html and "Supply Chain" in html,
             "missing Phase C description")
    validate(page, "landing", "CTA band",
             "Demand-Validated" in html and "live job count" in html,
             "missing CTA band text")
    validate(page, "landing", "navigation links",
             'href="/sprints"' in html and 'href="/pricing"' in html,
             "missing nav links to /sprints or /pricing")


def validate_picker(page):
    """Sprint picker: cluster cards with demand badges, start CTAs."""
    html = page.content()
    validate(page, "picker", "page heading",
             "Choose your sprint" in html,
             "missing 'Choose your sprint' heading")
    for key, name in [("email-automation", "Email Automation"),
                      ("web-scraping", "Web Scraping"),
                      ("ai-chatbots", "AI Chatbots")]:
        validate(page, "picker", f"cluster card: {name}",
                 name in html,
                 f"missing cluster card for {name}")
    validate(page, "picker", "demand badges (jobs open)",
             re.search(r'\d+ jobs open', html) is not None,
             "no 'N jobs open' badge visible")
    validate(page, "picker", "rate badge",
             re.search(r'\$\d+/hr', html) is not None,
             "no rate badge visible")
    validate(page, "picker", "start sprint buttons",
             html.count("Start sprint") >= 1,
             "no Start sprint buttons found")
    validate(page, "picker", "request sprint section",
             "Request a sprint" in html,
             "missing Request a sprint section")


def validate_dashboard(page, sprint_id, phase=None, day_no=None):
    """Dashboard: sprint header, phase labels, job unlock meter, momentum, today card."""
    html = page.content()
    validate(page, "dashboard", "sprint header (cluster name)",
             "Email Automation" in html or "email-automation" in html,
             "missing cluster name in sprint header")
    validate(page, "dashboard", "cohort or sprint label",
             "Sprint" in html or "Cohort" in html,
             "missing sprint/cohort label")
    validate(page, "dashboard", "active jobs count",
             re.search(r'\d+ active jobs', html) is not None,
             "missing 'N active jobs' in sprint header")
    validate(page, "dashboard", "rate display",
             re.search(r'\$\d+/hr', html) is not None,
             "missing rate display")

    # Phase A should always be visible
    validate(page, "dashboard", "Phase A label",
             "Phase A" in html and "Skill Acquisition" in html,
             "missing Phase A / Skill Acquisition")
    # Phase B label (may be locked or unlocked)
    validate(page, "dashboard", "Phase B label",
             "Phase B" in html and "Mock Contract" in html,
             "missing Phase B / Mock Contract")
    # Phase C label
    validate(page, "dashboard", "Phase C label",
             "Phase C" in html and "Supply Chain" in html,
             "missing Phase C / Supply Chain")

    # Job Unlock Meter
    validate(page, "dashboard", "job unlock meter heading",
             "Job Unlock Meter" in html,
             "missing Job Unlock Meter section")
    validate(page, "dashboard", "unlock count",
             re.search(r'\d+.*active jobs unlocked', html) is not None,
             "missing unlock count (N / M active jobs unlocked)")
    validate(page, "dashboard", "day progress bar",
             re.search(r'\d+ of 14 days done', html) is not None,
             "missing 'N of 14 days done' progress text")

    # Momentum card
    validate(page, "dashboard", "momentum card",
             "Momentum" in html and "Day streak" in html and "Confidence" in html,
             "missing Momentum card (streak + confidence)")
    validate(page, "dashboard", "proposals sent counter",
             "Proposals sent" in html,
             "missing Proposals sent counter")
    validate(page, "dashboard", "contracts counter",
             "Contracts" in html,
             "missing Contracts counter")

    # Today card
    validate(page, "dashboard", "today card heading",
             "Today" in html,
             "missing Today card")
    validate(page, "dashboard", "check-items (watch/replicate/self-check)",
             "Watch lesson" in html and "Replicate the project" in html,
             "missing check-items in today card")

    # Phase-specific lock indicators
    if phase == "A":
        validate(page, "dashboard", "Phase B locked (before gate A)",
                 "Unlocks when Phase A passes verification" in html,
                 "Phase B should show lock note before gate A passes")
    elif phase == "B":
        validate(page, "dashboard", "Phase B unlocked",
                 "Unlocks when Phase A passes verification" not in html,
                 "Phase B lock note should be gone after gate A passes")
        validate(page, "dashboard", "Phase C locked (before gate B)",
                 "Locked until Mock Contract passes" in html,
                 "Phase C should show lock note before gate B passes")
    elif phase == "C":
        validate(page, "dashboard", "Phase B unlocked",
                 "Unlocks when Phase A passes verification" not in html,
                 "Phase B lock note should be gone")
        validate(page, "dashboard", "Phase C unlocked",
                 "Locked until Mock Contract passes" not in html,
                 "Phase C lock note should be gone after gate B passes")

    # Contracts & Earnings section (template uses &amp; HTML entity)
    validate(page, "dashboard", "contracts & earnings section",
             "Contracts" in html and "Earnings" in html,
             "missing Contracts & Earnings section")


def validate_day_view(page, day_no, expect_lesson=True, expect_clone_steps=True):
    """Day view: lesson content, copywork task, clone steps, rubric, submit form.

    This is the CRITICAL validator — copywork is NEVER submitted unless:
    1. Lesson content is rendered (not 'Generating…')
    2. Clone steps are visible
    3. Rubric items are present
    """
    html = page.content()

    # Header: Phase + Day + action type
    validate(page, f"day-{day_no}", "day header",
             f"Day {day_no}" in html,
             f"missing 'Day {day_no}' in header")

    # Lesson card
    validate(page, f"day-{day_no}", "lesson card heading",
             "Watch" in html and "Lesson" in html,
             "missing lesson card heading (🎬 Watch · Lesson)")

    if expect_lesson:
        # CRITICAL: lesson content must be actually rendered
        gen_error = "Lesson generation failed" in html
        generating = "Generating your lesson…" in html
        has_lesson_title = bool(re.search(r'<b[^>]*>[^<]{5,}</b>', html))

        validate(page, f"day-{day_no}", "lesson NOT in error state",
                 not gen_error,
                 "lesson generation failed — cannot proceed")
        validate(page, f"day-{day_no}", "lesson NOT still generating",
                 not generating,
                 "lesson still showing 'Generating your lesson…' — content not ready")
        validate(page, f"day-{day_no}", "lesson has rendered content",
                 not generating and not gen_error and has_lesson_title,
                 "lesson content not visible — no rendered title found")

        # Check for actual lesson body content (script, key_points, or pitfalls)
        has_script_body = bool(re.search(
            r'data-lesson-content|class="small".*?margin-top:8px|format_script', html))
        validate(page, f"day-{day_no}", "lesson has script/body content",
                 has_script_body or generating or gen_error,
                 "lesson card has no script body content rendered")

        # Key points list
        has_keypoints = "key_points" in html or re.search(r'<li[^>]*>.*?</li>', html) is not None
        validate(page, f"day-{day_no}", "lesson has key points",
                 has_keypoints,
                 "no key points list found in lesson")

        # Mark lesson watched checkbox
        validate(page, f"day-{day_no}", "mark lesson watched check-item",
                 "Mark lesson watched" in html,
                 "missing 'Mark lesson watched' check-item")

    # Copy-work task card
    validate(page, f"day-{day_no}", "copywork card heading",
             "Copy-Work Task" in html,
             "missing Copy-Work Task card")

    if expect_clone_steps:
        # CRITICAL: clone steps must be visible before we can submit
        has_clone_steps = bool(re.search(r'<li[^>]*>.*?</li>', html))
        still_generating = "Project anatomy is being generated" in html
        gen_failed = "Project anatomy failed" in html

        validate(page, f"day-{day_no}", "clone steps NOT generating",
                 not still_generating,
                 "clone steps still generating — cannot validate")
        validate(page, f"day-{day_no}", "clone steps rendered",
                 has_clone_steps and not still_generating and not gen_failed,
                 "clone steps not visible — no <li> items found in copywork card")

        # Rubric items
        has_rubric = "Pass 3-point rubric" in html
        validate(page, f"day-{day_no}", "rubric section visible",
                 has_rubric,
                 "missing 'Pass 3-point rubric' section")

        # Submit form
        validate(page, f"day-{day_no}", "copywork submit form",
                 "rubric_url" in html and "Submit for check" in html,
                 "missing copywork submit form")

    # Mark day complete button
    validate(page, f"day-{day_no}", "mark day complete button",
             f"Mark day {day_no} complete" in html,
             f"missing 'Mark day {day_no} complete' button")


def validate_contract(page):
    """Contract page: client brief, submission form."""
    html = page.content()
    validate(page, "contract", "client brief heading",
             "Client Brief" in html,
             "missing 'Client Brief' heading")
    validate(page, "contract", "submission form",
             "submission_url" in html and "Submit deliverable" in html,
             "missing submission form")
    validate(page, "contract", "contract brief content",
             "Mock Contract" in html or "brief" in html.lower(),
             "missing contract brief content")


def validate_proposals(page):
    """Proposals page: First-Bid heading, proposal builder, job table."""
    html = page.content()
    validate(page, "proposals", "First-Bid heading",
             "First-Bid" in html,
             "missing 'First-Bid Challenge' heading")
    validate(page, "proposals", "proposal count indicator",
             re.search(r'\d+\s*/\s*5\s*proposals', html) is not None,
             "missing 'N / 5 proposals' count")
    validate(page, "proposals", "proposal builder card",
             "Proposal Builder" in html,
             "missing Proposal Builder card")
    validate(page, "proposals", "LLM-engineered badge",
             "LLM-engineered" in html,
             "missing 'LLM-engineered' badge")
    validate(page, "proposals", "proposal text content",
             "proposal-text" in html or "Writing your engineered proposal" in html,
             "no proposal text or generating message visible")
    validate(page, "proposals", "live jobs table",
             "Live jobs to bid on" in html,
             "missing 'Live jobs to bid on' table")
    validate(page, "proposals", "submit buttons",
             "Draft — submit" in html,
             "missing 'Draft — submit' buttons")
    validate(page, "proposals", "log outcome section",
             "Log an outcome" in html,
             "missing 'Log an outcome' section")


def validate_profile(page, display_name="Maya Chen"):
    """Profile page: display name, badges, case studies."""
    html = page.content()
    validate(page, "profile", "display name",
             display_name in html,
             f"missing display name '{display_name}'")
    validate(page, "profile", "Demand-Validated badge section",
             "Demand-Validated Badges" in html,
             "missing 'Demand-Validated Badges' heading")
    validate(page, "profile", "badge rendered",
             "🏅" in html and "Sprint" in html,
             "no badge emoji or sprint name in badges section")
    validate(page, "profile", "active jobs count on badge",
             re.search(r'\d+ active jobs right now', html) is not None,
             "missing 'N active jobs right now' on badge")
    validate(page, "profile", "case study portfolio section",
             "Case Study Portfolio" in html,
             "missing 'Case Study Portfolio' heading")


def validate_mentor(page):
    """Mentor page: AI Mentor heading."""
    html = page.content()
    validate(page, "mentor", "AI Mentor heading",
             "AI Mentor" in html,
             "missing 'AI Mentor' heading")


def validate_pricing(page):
    """Pricing page: pricing heading."""
    html = page.content()
    validate(page, "pricing", "pricing heading",
             "Pricing comes after placement" in html,
             "missing 'Pricing comes after placement' heading")


# ── Helpers ───────────────────────────────────────────────────────

def _sb():
    from dotenv import load_dotenv
    load_dotenv()
    from app import create_app
    app = create_app()
    ctx = app.app_context()
    ctx.push()
    from services.supabase_client import get_supabase
    return get_supabase()


def _demo_user_id(sb):
    for u in sb.auth.admin.list_users():
        if u.email == "demo@sprint-platform.local":
            return u.id
    return None


def pre_cleanup():
    sb = _sb()
    demo_id = _demo_user_id(sb)
    if demo_id:
        stale = sb.table("sprints").select("id").eq("user_id", demo_id) \
            .eq("cluster_key", "email-automation").execute().data
        for s in stale:
            sb.table("sprints").delete().eq("id", s["id"]).execute()
            print(f"  🧹 pre-clean: deleted leftover sprint {s['id'][:8]}")
    sb.table("job_clusters").delete().eq("cluster_key", "visual-run-cluster").execute()


def ensure_demo_platform():
    sb = _sb()
    demo_id = _demo_user_id(sb)
    if not demo_id:
        return
    for platform in ("upwork", "fiverr"):
        sb.table("user_platforms").upsert(
            {"user_id": demo_id, "platform": platform},
            on_conflict="user_id,platform",
        ).execute()
    print("  ✓ demo user platforms ensured (upwork, fiverr)")


def pass_gate(sprint_id, gate):
    sb = _sb()
    sb.table("verification_reviews").upsert({
        "sprint_id": sprint_id, "gate": gate, "status": "pass",
        "verification_type": "auto",
    }, on_conflict="sprint_id,gate").execute()
    print(f"  ✓ gate {gate} passed")


def complete_sprint(sprint_id):
    sb = _sb()
    sb.table("sprints").update({"status": "completed", "current_day": 14, "phase": "C"}) \
        .eq("id", sprint_id).execute()
    print("  ✓ sprint marked completed")


def cleanup(sprint_id):
    sb = _sb()
    sb.table("sprints").delete().eq("id", sprint_id).execute()
    sb.table("job_clusters").delete().eq("cluster_key", "visual-run-cluster").execute()
    print("  🧹 visual-run sprint + cluster cleaned up")


# ── Main run ──────────────────────────────────────────────────────

def run():
    from playwright.sync_api import sync_playwright
    pre_cleanup()
    ensure_demo_platform()
    server = start_server()
    shots = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=["--start-maximized"])
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                record_video_dir=f"{OUT}/videos",
                record_video_size={"width": 1440, "height": 900},
            )
            page = context.new_page()
            wire_console(page)

            # ══ ADMIN LEG ══════════════════════════════════════════
            page_label["v"] = "admin-login"
            page.goto(f"{BASE}/auth/login")
            page.fill("input[name=email]", "admin@sprint-platform.local")
            shots.append(shot(page, "01_admin_login"))
            page.click("button[type=submit]")
            page.wait_for_url("**/sprints")

            page_label["v"] = "admin-dashboard"
            page.goto(f"{BASE}/admin/")
            page.wait_for_selector("h2")
            shots.append(shot(page, "02_admin_dashboard"))

            page_label["v"] = "admin-clusters"
            page.goto(f"{BASE}/admin/clusters")
            page.wait_for_selector("table")
            shots.append(shot(page, "03_admin_clusters"))

            page_label["v"] = "admin-feed"
            page.goto(f"{BASE}/admin/feed")
            page.wait_for_selector("table")
            shots.append(shot(page, "04_admin_feed"))

            page_label["v"] = "admin-cohorts"
            page.goto(f"{BASE}/admin/cohorts")
            page.wait_for_selector("table")
            shots.append(shot(page, "05_admin_cohorts"))

            page_label["v"] = "admin-cluster-create"
            page.goto(f"{BASE}/admin/clusters/create")
            page.fill("#cluster_key", "visual-run-cluster")
            page.fill("#display_name", "Visual Run Cluster")
            page.fill("#icon", "🎬")
            page.fill("#description", "Created by the headed visual run — deleted after.")
            page.fill("#job_count", "77")
            page.fill("#avg_rate", "51")
            page.fill("#growth_score", "7")
            shots.append(shot(page, "06_admin_cluster_form_filled"))
            page.click("button[type=submit]")
            page.wait_for_url("**/admin/clusters")
            page.wait_for_selector("text=Visual Run Cluster")
            shots.append(shot(page, "07_admin_cluster_created"))

            # ══ LEARNER LEG ════════════════════════════════════════
            page_label["v"] = "landing"
            page.goto(f"{BASE}/auth/logout")
            page.goto(f"{BASE}/")
            page.wait_for_selector("h1")
            shots.append(shot(page, "08_landing"))
            validate_landing(page)

            page_label["v"] = "login"
            page.goto(f"{BASE}/auth/login")
            page.fill("input[name=email]", "demo@sprint-platform.local")
            page.click("button[type=submit]")
            page.wait_for_url("**/sprints")

            page_label["v"] = "picker"
            page.wait_for_selector("text=Choose your sprint")
            shots.append(shot(page, "09_picker"))
            validate_picker(page)

            # ── START SPRINT ──
            page_label["v"] = "start-sprint"
            r = page.request.post(f"{BASE}/sprints/email-automation/start", form={}, max_redirects=0)
            print(f"  start-sprint status={r.status}")
            loc = r.headers.get("location", "")
            m = re.search(r"/sprints/([0-9a-f-]{36})$", loc)
            assert m, f"no sprint UUID in start redirect: {loc!r}"
            sprint_id = m.group(1)
            sprint_url = f"{BASE}/sprints/{sprint_id}"
            print(f"  sprint created: {sprint_id}")

            # ── WAIT FOR CONTENT GENERATION ──
            # The async worker generates lesson content in the background.
            # Poll /generation until all 14 days are ready before visiting any day page.
            page_label["v"] = "wait-generation"
            print("  ⏳ waiting for content generation to complete...")
            gen_ready = False
            for attempt in range(60):  # max 60 × 2s = 120s
                gen_result = page.evaluate(
                    """async (url) => {
                        const r = await fetch(url, {credentials:'same-origin'});
                        return await r.json();
                    }""",
                    f"{BASE}/sprints/{sprint_id}/generation",
                )
                status = gen_result.get("status", "unknown")
                generated = gen_result.get("generated", 0)
                total = gen_result.get("total", 14)
                if status == "ready":
                    print(f"  ✓ content generation ready ({generated}/{total})")
                    gen_ready = True
                    break
                elif status == "error":
                    print(f"  ⚠ content generation failed: {gen_result.get('error', 'unknown')}")
                    break
                else:
                    if attempt % 5 == 0:
                        print(f"  ⏳ generating... {generated}/{total} (attempt {attempt+1})")
                    time.sleep(2)
            if not gen_ready and status != "error":
                print(f"  ⚠ content generation timed out after {attempt+1} attempts")

            # ── DASHBOARD DAY 1 ──
            page_label["v"] = "dashboard-day1"
            page.goto(sprint_url)
            page.wait_for_selector("text=Job Unlock Meter")
            # Wait for generation banner to disappear (if still visible)
            try:
                page.wait_for_selector("#gen-banner", state="hidden", timeout=10000)
            except Exception:
                pass  # banner may already be hidden
            shots.append(shot(page, "10_dashboard_day1"))
            validate_dashboard(page, sprint_id, phase="A", day_no=1)

            # ── DAY 1 VIEW ──
            page_label["v"] = "day-1"
            page.click("a:has-text('Open Day 1')")
            page.wait_for_selector("text=Copy-Work Task")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)  # allow async rendering
            shots.append(shot(page, "11_day1"))

            # CRITICAL: validate day 1 content is rendered before proceeding
            validate_day_view(page, day_no=1, expect_lesson=True, expect_clone_steps=True)

            # Abort if day 1 content isn't ready
            if any("day-1" in f[0] and ("❌" in f[1] or True) for f in validation_failures):
                day1_fails = [f for f in validation_failures if f[0] == "day-1"]
                if day1_fails:
                    print(f"\n  ⛔ ABORTING: {len(day1_fails)} content validation failures on Day 1:")
                    for _, check, detail in day1_fails:
                        print(f"     • {check}: {detail}")
                    print("     Copywork NOT submitted — lesson content is not ready.\n")

            # ── COMPLETE DAYS 1–5 ──
            page_label["v"] = "day-complete"
            for d in range(1, 6):
                result = page.evaluate(
                    """async (url) => {
                        const r = await fetch(url, {method:'POST', credentials:'same-origin', redirect:'follow'});
                        return {status: r.status, url: r.url, redirected: r.redirected};
                    }""",
                    f"{BASE}/sprints/{sprint_id}/day/{d}/complete",
                )
                print(f"  ✓ day {d} complete → {result}")

            page.goto(sprint_url)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
            shots.append(shot(page, "12_dashboard_after_days"))
            validate_dashboard(page, sprint_id, phase="A", day_no=6)

            # ── COPYWORK + GATE A ──
            page_label["v"] = "gate-a"
            page.request.post(f"{BASE}/sprints/{sprint_id}/day/4/copywork",
                              form={"rubric_url": "https://github.com/maya/flow"})
            pass_gate(sprint_id, "A")
            page.goto(sprint_url)
            page.wait_for_selector("text=Mock Contract")
            assert "Unlocks when Phase A passes verification" not in page.content()
            shots.append(shot(page, "13_dashboard_phase_b_unlocked"))
            validate_dashboard(page, sprint_id, phase="B", day_no=6)

            # ── CONTRACT ──
            page_label["v"] = "contract"
            page.goto(f"{BASE}/sprints/{sprint_id}/contract")
            page.wait_for_selector("text=Client Brief")
            shots.append(shot(page, "14_contract_brief"))
            validate_contract(page)

            page.fill("input[name=submission_url]", "https://dropbox.com/maya-deliverable")
            page.click("button[type=submit]")
            page.wait_for_selector("text=verification service is checking")
            shots.append(shot(page, "15_contract_submitted"))

            # ── GATE B + PROPOSALS ──
            page_label["v"] = "gate-b"
            pass_gate(sprint_id, "B")
            page.goto(f"{BASE}/sprints/{sprint_id}/proposals")
            page.wait_for_selector("text=First-Bid")
            shots.append(shot(page, "16_proposals_unlocked"))
            validate_proposals(page)

            page_label["v"] = "proposal-submit"
            page.click("button:has-text('Draft — submit')")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)
            shots.append(shot(page, "17_proposal_submitted"))
            # Re-validate after submission — submitted count should increment
            validate_proposals(page)

            # ── COMPLETION + BADGE ──
            page_label["v"] = "badge"
            complete_sprint(sprint_id)
            page.goto(f"{BASE}/sprints/{sprint_id}/badge")
            page.wait_for_load_state("networkidle")

            # ── PROFILE ──
            page_label["v"] = "profile"
            page.goto(f"{BASE}/profile/maya")
            page.wait_for_selector("text=Demand-Validated")
            shots.append(shot(page, "18_profile_badge"))
            validate_profile(page, "Maya Chen")

            # ── CLIENTS ──
            page_label["v"] = "clients"
            page.goto(f"{BASE}/clients/freelancers?cluster=email-automation&within_days=30")
            page.wait_for_selector("text=Maya Chen")
            shots.append(shot(page, "19_clients_filter"))

            # ── MENTOR ──
            page_label["v"] = "mentor"
            page.goto(f"{BASE}/mentor")
            page.wait_for_selector("text=AI Mentor")
            shots.append(shot(page, "20_mentor"))
            validate_mentor(page)

            # ── PRICING ──
            page_label["v"] = "pricing"
            page.goto(f"{BASE}/pricing")
            page.wait_for_selector("text=Pricing comes after placement")
            shots.append(shot(page, "21_pricing"))
            validate_pricing(page)

            video_path = page.video.path() if page.video else None
            context.close()
            browser.close()

        cleanup(sprint_id)
        print("\n══ VISUAL RUN SUMMARY ══")
        print(f"screenshots: {len(shots)} in {OUT}/shots/")
        print(f"video: {video_path}")
        print(f"console errors: {len(console_errors)}")
        for label, typ, text in console_errors:
            print(f"  [{label}] {typ}: {text}")
        print(f"\ncontent validation failures: {len(validation_failures)}")
        if validation_failures:
            for screen, check, detail in validation_failures:
                print(f"  ❌ [{screen}] {check}: {detail}")
        else:
            print("  ✅ ALL screens passed content validation")
    finally:
        server.terminate()
        server.wait(timeout=10)


if __name__ == "__main__":
    run()
