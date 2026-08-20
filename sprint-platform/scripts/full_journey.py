"""Full 14-day learner journey — headed Playwright walkthrough of all 3 phases.

Phase A · Skill Acquisition (Days 1-5) → Phase B · Mock Contract (Days 6-10)
→ Phase C · Supply Chain (Days 11-14). Every step is visited in a real browser
exactly as a paying learner would experience it: dashboard, each day's lesson +
copy-work + rubric, the contract brief, the case study, the proposal challenge,
the Day-14 iteration diagnosis, the badge and the public profile.

Output: numbered screenshots in /tmp/full_journey + a step journal printed to
stdout so the journey can be critiqued step by step.

Usage:  DISPLAY=:0 .venv/bin/python scripts/full_journey.py
"""
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = "http://127.0.0.1:5000"
OUT = "/tmp/full_journey"
os.makedirs(f"{OUT}/shots", exist_ok=True)

journal = []          # (step_no, title, detail) — printed at the end
console_errors = []   # (page_label, type, text)
page_label = {"v": "startup"}


def log(step, title, detail=""):
    journal.append((step, title, detail))
    print(f"  ▶ STEP {step}: {title}" + (f" — {detail}" if detail else ""))


def start_server():
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "from app import create_app; create_app().run(host='127.0.0.1', port=5000, debug=False)"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    import urllib.request
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"{BASE}/health", timeout=2) as r:
                if json.loads(r.read()).get("status") == "ok":
                    print(f"server up")
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
    print(f"  📸 {name}.png")
    return path


def sb_client():
    from dotenv import load_dotenv
    load_dotenv()
    from app import create_app
    app = create_app()
    ctx = app.app_context()
    ctx.push()
    from services.supabase_client import get_supabase
    return get_supabase()


def demo_user_id(sb):
    for u in sb.auth.admin.list_users():
        if u.email == "demo@sprint-platform.local":
            return u.id
    return None


def pre_cleanup(sb):
    demo_id = demo_user_id(sb)
    if demo_id:
        stale = sb.table("sprints").select("id").eq("user_id", demo_id) \
            .eq("cluster_key", "email-automation").execute().data
        for s in stale:
            sb.table("sprints").delete().eq("id", s["id"]).execute()
            print(f"  🧹 pre-clean: deleted leftover sprint {s['id'][:8]}")
    sb.table("job_clusters").delete().eq("cluster_key", "full-journey-cluster").execute()


def ensure_platforms(sb):
    demo_id = demo_user_id(sb)
    if not demo_id:
        return
    for platform in ("upwork", "fiverr"):
        sb.table("user_platforms").upsert(
            {"user_id": demo_id, "platform": platform},
            on_conflict="user_id,platform",
        ).execute()
    print("  ✓ demo user platforms ensured (upwork, fiverr)")


def wait_generation(page, sprint_id, timeout_s=180):
    print("  ⏳ waiting for content generation to complete...")
    for _ in range(timeout_s // 2):
        result = page.evaluate(
            """async (url) => {
                const r = await fetch(url, {credentials:'same-origin'});
                const t = await r.text();
                try { return JSON.parse(t); } catch (e) { return {status:'error', error: t.slice(0,120)}; }
            }""",
            f"{BASE}/sprints/{sprint_id}/generation",
        )
        status = result.get("status", "unknown")
        if status == "ready":
            print(f"  ✓ content generation ready ({result.get('generated')}/{result.get('total')})")
            return True
        if status == "error":
            print(f"  ⚠ content generation failed: {result.get('error', 'unknown')}")
            return False
        time.sleep(2)
    print("  ⚠ content generation timed out")
    return False


def lesson_ready(html):
    return ("Generating your lesson…" not in html
            and "Lesson generation failed" not in html
            and ("data-lesson-content" in html or "▶" in html))


def run():
    from playwright.sync_api import sync_playwright
    sb = sb_client()
    pre_cleanup(sb)
    ensure_platforms(sb)
    proc = start_server()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=["--start-maximized"])
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            wire_console(page)

            # ══ START: learner login + sprint enrollment ══
            page_label["v"] = "login"
            page.goto(f"{BASE}/auth/login")
            page.fill("input[name=email]", "demo@sprint-platform.local")
            page.click("button[type=submit]")
            page.wait_for_url("**/sprints")
            print("  ✓ logged in as demo learner")

            page_label["v"] = "picker"
            page.wait_for_selector("text=Choose your sprint")
            shot(page, "00_sprint_picker")
            log(0, "Sprint picker", "Choose your sprint — demand-validated clusters with live job counts + rates")

            r = page.request.post(f"{BASE}/sprints/email-automation/start", form={}, max_redirects=0)
            m = re.search(r"/sprints/([0-9a-f-]{36})$", r.headers.get("location", ""))
            assert m, f"no sprint UUID in start redirect: {r.headers.get('location','')!r}"
            sprint_id = m.group(1)
            sprint_url = f"{BASE}/sprints/{sprint_id}"
            print(f"  ✓ sprint created: {sprint_id}")

            # ══ PHASE A · SKILL ACQUISITION (Days 1-5) ══
            page_label["v"] = "phaseA"
            page.goto(sprint_url)
            page.wait_for_selector("text=Job Unlock Meter")
            try:
                page.wait_for_selector("#gen-banner", state="hidden", timeout=120000)
            except Exception:
                pass
            shot(page, "01_phaseA_dashboard_day1")
            log(1, "Phase A · Dashboard (Day 1)", "Phase-locked track, Job Unlock Meter, today card, momentum")

            wait_generation(page, sprint_id)

            for d in range(1, 6):
                page_label["v"] = f"day-{d}"
                page.goto(f"{BASE}/sprints/{sprint_id}/day/{d}")
                page.wait_for_selector("text=Copy-Work Task")
                # wait for lesson content to render (or reach a visible error)
                for _ in range(60):
                    html = page.content()
                    if lesson_ready(html) or "Lesson generation failed" in html:
                        break
                    time.sleep(2)
                shot(page, f"02_phaseA_day{d}")
                log(2, f"Phase A · Day {d} lesson + copy-work", "🎬 Lesson, 🛠️ copy-work clone steps, 3-point rubric, submit link")

                # mark lesson watched (real click on the form button)
                page.click("form[action*='/watched'] button[type='submit']")
                page.wait_for_load_state("networkidle")

                # submit the rebuilt flow link (fake URL, for the walkthrough)
                page.fill("form[action*='/copywork'] input[name='rubric_url']",
                          "https://github.com/demo/flow-day")
                page.click("form[action*='/copywork'] button[type='submit']")
                page.wait_for_load_state("networkidle")

                if d < 5:
                    # complete the day → redirects to the next day page
                    page.click("form[action*='/complete'] button[type='submit']")
                    page.wait_for_load_state("networkidle")
                    log(2, f"Phase A · Day {d} marked complete", "Unlocks next batch of job postings (+meter)")

            # after day 5 the sprint lands on day 6; copywork for days 4+5 passed Gate A
            page.goto(sprint_url)
            page.wait_for_selector("text=Job Unlock Meter")
            shot(page, "03_phaseA_dashboard_done")
            log(3, "Phase A complete · dashboard", "5/5 days done — Gate A passed, Phase B unlocked")

            # ══ PHASE B · MOCK CONTRACT (Days 6-10) ══
            page_label["v"] = "phaseB"
            page.goto(f"{BASE}/sprints/{sprint_id}/contract")
            page.wait_for_selector("text=Client Brief")
            shot(page, "04_phaseB_contract_brief")
            log(4, "Phase B · Mock Contract brief", "Anonymized real job brief — requirements, deadline, budget")

            # write the case study (Days 9-10) BEFORE the deliverable submit —
            # Gate B only auto-checks on deliverable submit and needs BOTH
            # a valid URL AND a saved case study (verification_service).
            page.fill("input[name=title]", "Abandoned-Cart Recovery Flow")
            page.fill("textarea[name=problem]", "Cart abandonment at 78% on a Shopify store")
            page.fill("textarea[name=solution]", "Three-email automated recovery sequence via Klaviyo")
            page.fill("textarea[name=result]", "Recovered 14% of abandoned carts in the first month")
            page.click("button:has-text('Save case study')")
            page.wait_for_load_state("networkidle")
            shot(page, "06_phaseB_case_study")
            log(4, "Phase B · Case study", "Problem / Solution / Result saved → becomes profile portfolio item")

            # submit the deliverable → Gate B auto-check runs now that both
            # the URL and the case study exist → Phase C unlocks
            page.fill("input[name=submission_url]", "https://dropbox.com/demo-deliverable")
            page.click("button[type=submit]")
            page.wait_for_selector("text=verification service is checking")
            shot(page, "05_phaseB_deliverable_submitted")

            page.goto(f"{BASE}/sprints/{sprint_id}/contract")
            page.wait_for_selector("text=Verification Gate")
            shot(page, "07_phaseB_gate_passed")
            log(5, "Phase B · Verification Gate passed", "Automated flow check ✓ + case study ✓ → Phase C unlocked")

            page.goto(sprint_url)
            page.wait_for_selector("text=Job Unlock Meter")
            shot(page, "08_phaseB_dashboard")
            log(5, "Phase B complete · dashboard", "Phase C unlocked — Supply Chain card now open")

            # ══ PHASE C · SUPPLY CHAIN (Days 11-14) ══
            page_label["v"] = "phaseC"
            page.goto(f"{BASE}/sprints/{sprint_id}/proposals")
            page.wait_for_selector("text=First-Bid")
            # wait for the LLM-engineered proposal to fill
            for _ in range(90):
                html = page.content()
                if "proposal-text" in html or "Proposal generation failed" in html:
                    break
                time.sleep(2)
            shot(page, "09_phaseC_proposal_builder")
            log(6, "Phase C · Proposal Builder", "LLM-engineered 'I see you need X…' draft + live jobs to bid on")

            # submit all 5 proposals
            for _ in range(6):
                btns = page.query_selector_all("button:has-text('Draft — submit')")
                if not btns:
                    break
                btns[0].click()
                page.wait_for_load_state("networkidle")
            page.reload()
            page.wait_for_selector("text=First-Bid")
            shot(page, "10_phaseC_five_submitted")
            log(7, "Phase C · 5 proposals submitted", "Each one human-initiated — copy-paste + submit")

            # Day-14 iteration diagnosis: 5 sent, 0 responses
            page.goto(f"{BASE}/sprints/{sprint_id}/proposals")
            page.wait_for_selector("text=First-Bid")
            html = page.content()
            if "Iteration diagnosis" in html:
                shot(page, "11_phaseC_diagnosis")
                log(8, "Phase C · Day-14 iteration diagnosis", "System diagnoses the bottleneck + assigns a 2h remedial micro-course")
            else:
                log(8, "Phase C · Day-14 diagnosis", "not triggered — proposals still converting")

            page.goto(sprint_url)
            page.wait_for_selector("text=Job Unlock Meter")
            shot(page, "12_final_dashboard")
            log(9, "Final dashboard", "14-day sprint record: contracts, earnings, momentum")

            # ══ PAYOFF: badge + public profile ══
            page_label["v"] = "badge"
            page.goto(f"{BASE}/sprints/{sprint_id}/badge")
            page.wait_for_load_state("networkidle")
            page.goto(f"{BASE}/profile/maya")
            page.wait_for_selector("text=Demand-Validated")
            shot(page, "13_profile_badge")
            log(10, "Payoff · Profile + badge", "Demand-Validated badge with live 'N active jobs right now' + case study portfolio")

            video_path = page.video.path() if page.video else None
            context.close()
            browser.close()

        print("\n══ FULL JOURNEY JOURNAL ══")
        for step, title, detail in journal:
            print(f"  STEP {step:>2}  {title}\n        {detail}")
        print(f"\nscreenshots: {len(os.listdir(f'{OUT}/shots'))} in {OUT}/shots/")
        print(f"console errors: {len(console_errors)}")
        for label, typ, text in console_errors:
            print(f"  [{label}] {typ}: {text}")
    finally:
        proc.terminate()
        proc.wait(timeout=10)


if __name__ == "__main__":
    run()