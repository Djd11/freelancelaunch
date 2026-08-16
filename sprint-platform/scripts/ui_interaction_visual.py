"""Headed Playwright visual run — UI interaction points (ui-interaction.feature).

Runs a real browser on DISPLAY=:0 with video + per-screen screenshots. Walks
every page and exercises the interaction points the BDD suite asserts at the
HTTP level: check-items/checkboxes, submit buttons/forms, and landing pages
per eng-spec J1/J2/J7. Creates a throwaway sprint, then cleans up.

Usage:  DISPLAY=:0 .venv/bin/python scripts/ui_interaction_visual.py
"""
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = "http://127.0.0.1:5001"
OUT = "/tmp/ui_interaction_visual"
os.makedirs(f"{OUT}/shots", exist_ok=True)
os.makedirs(f"{OUT}/videos", exist_ok=True)

console_errors = []   # (page_label, type, text)
page_label = {"v": "startup"}


def start_server():
    # Log to a file, NOT a pipe: the dev-server request log would fill an
    # undrained 64KB stdout pipe mid-run and block the server (flaky POSTs
    # that redirect to the dashboard instead of completing).
    logf = open(f"{OUT}/server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "from app import create_app; "
         "create_app().run(host='127.0.0.1', port=5001, debug=False, threaded=False)"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        stdout=logf, stderr=subprocess.STDOUT,
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
            loc = msg.location or {}
            detail = f" ({loc.get('url', '')})" if loc.get("url") else ""
            console_errors.append((page_label["v"], msg.type, msg.text[:200] + detail))
    def on_pageerror(err):
        console_errors.append((page_label["v"], "pageerror", str(err)[:200]))
    def on_response(resp):
        if resp.status >= 400:
            console_errors.append((page_label["v"], f"http-{resp.status}",
                                   f"{resp.request.resource_type} {resp.url}"))
    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    page.on("response", on_response)


def shot(page, name):
    path = f"{OUT}/shots/{name}.png"
    page.screenshot(path=path, full_page=True)
    print(f"  📸 {name}.png  ({page.url})")
    return path


def check(page, label, cond, detail=""):
    status = "OK" if cond else "FAIL"
    print(f"  {status}  {label}" + (f"  ({detail})" if detail else ""))
    if not cond:
        raise AssertionError(f"{label}: {detail}")


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

            # ══ LANDING PAGES (public, eng-spec J1) ═══════════════
            page_label["v"] = "landing"
            page.goto(f"{BASE}/")
            page.wait_for_selector("h1")
            check(page, "landing headline", "Stop learning skills" in page.content())
            check(page, "landing start CTA", page.locator('a[href="/sprints"]').count() >= 1)
            check(page, "landing #how anchor + link",
                  page.locator('a[href="#how"]').count() >= 1 and page.locator('#how').count() >= 1)
            shots.append(shot(page, "01_landing"))

            page_label["v"] = "topics"
            page.goto(f"{BASE}/topics")   # goto follows the redirect chain
            # Anonymous visitor: /topics → /sprints (auth-gated) → /auth/login
            check(page, "topics redirects toward sprint catalog",
                  "/sprints" in page.url or "/auth/login" in page.url)
            shots.append(shot(page, "02_topics_redirect"))

            page_label["v"] = "pricing"
            page.goto(f"{BASE}/pricing")
            page.wait_for_load_state("networkidle")
            check(page, "pricing renders", "Pricing" in page.content())
            check(page, "pricing no dead links", 'href="#"' not in page.content())
            shots.append(shot(page, "03_pricing"))

            page_label["v"] = "clients-public"
            page.goto(f"{BASE}/clients/freelancers?cluster=email-automation&within_days=30")
            page.wait_for_load_state("networkidle")
            check(page, "clients filter renders public", "Filter" in page.content())
            shots.append(shot(page, "04_clients_filter"))

            # ══ LOGIN → PICKER ════════════════════════════════════
            page_label["v"] = "login"
            page.goto(f"{BASE}/auth/login")
            page.fill("input[name=email]", "demo@sprint-platform.local")
            page.click("button[type=submit]")
            page.wait_for_url("**/sprints")
            check(page, "login form submits → picker", "Choose your sprint" in page.content())
            shots.append(shot(page, "05_picker"))

            # ══ CREATE A THROWAWAY SPRINT ═════════════════════════
            page_label["v"] = "start-sprint"
            r = page.request.post(f"{BASE}/sprints/email-automation/start", data={}, max_redirects=0)
            loc = r.headers.get("location", "")
            m = re.search(r"/sprints/([0-9a-f-]{36})$", loc)
            assert m, f"start POST status={r.status} location={loc!r} (auth-gated?)"
            sprint_id = m.group(1)
            sprint_url = f"{BASE}/sprints/{sprint_id}"
            print(f"  sprint created: {sprint_id}")
            page.goto(sprint_url)
            page.wait_for_selector("text=Job Unlock Meter")
            shots.append(shot(page, "06_dashboard"))

            # ══ DASHBOARD: check-items + submit buttons ═══════════
            page_label["v"] = "dashboard-checkitems"
            content = page.content()
            check(page, "watch-lesson check-item done", "check-item done" in content)
            check(page, "replicate + self-check items present",
                  "Replicate the project" in content and "Self-check vs rubric" in content)
            # Add-contract submit button (all 5 fields) → earnings roll-up
            page_label["v"] = "contract-add-form"
            page.fill("input[aria-label='Client name']", "Visual Client")
            page.fill("input[aria-label='Project title']", "Email automation")
            page.fill("input[aria-label='Contract value']", "300")
            page.fill("input[aria-label='Hours worked']", "20")
            page.fill("input[aria-label='Platform']", "upwork")
            shots.append(shot(page, "07_add_contract_filled"))
            page.click("button:has-text('Add contract')")
            page.wait_for_selector("td:has-text('Visual Client')", timeout=10000)  # form POST reloads the page
            check(page, "contract row rendered", "Visual Client" in page.content())
            check(page, "contract roll-up shows $300", "$300" in page.content())
            # Contract complete CTA (POST /contract/<id>/complete)
            page_label["v"] = "contract-complete"
            page.click("button:has-text('Mark complete')")
            page.wait_for_selector("span.badge:has-text('completed')", timeout=10000)
            check(page, "contract marked complete", "completed" in page.content())

            # ══ DAY VIEW: 3 check-items + both submit buttons ═════
            page_label["v"] = "day-view"
            page.goto(f"{BASE}/sprints/{sprint_id}/day/1")
            page.wait_for_selector("text=Copy-Work Task")
            content = page.content()
            check(page, "day check-items present",
                  "Mark lesson watched" in content and "Replicate from scratch" in content
                  and "Pass 3-point rubric" in content)
            shots.append(shot(page, "08_day1_checkitems"))
            # Submit-for-check button
            page_label["v"] = "day-copywork-submit"
            page.click("button:has-text('Submit for check')")
            page.wait_for_load_state("networkidle")
            check(page, "copywork submit returns to day view", "/day/1" in page.url)
            # Mark-day-complete button (POST returns JSON; reload shows the banner)
            page_label["v"] = "day-complete"
            page.click("button:has-text('Mark day 1 complete')")
            page.wait_for_load_state("networkidle")
            page.goto(f"{BASE}/sprints/{sprint_id}/day/1")
            page.wait_for_load_state("networkidle")
            check(page, "day complete banner", "job postings unlocked" in page.content())
            shots.append(shot(page, "09_day_completed"))

            # ══ MOCK CONTRACT: 2 check-items + submit + case-study ═
            page_label["v"] = "contract"
            page.goto(f"{BASE}/sprints/{sprint_id}/contract")
            page.wait_for_selector("text=Client Brief")
            content = page.content()
            check(page, "contract check-items present",
                  "Automated flow check" in content and "Case study written" in content)
            shots.append(shot(page, "09_contract_checkitems"))
            page_label["v"] = "contract-submit"
            page.fill("input[name=submission_url]", "https://dropbox.com/visual-deliverable")
            page.click("button[type=submit]")
            page.wait_for_load_state("networkidle")
            check(page, "contract submit accepted", "verification" in page.content().lower())
            page_label["v"] = "case-study-form"
            page.fill("input[aria-label='Case study title']", "Visual Case Study")
            page.fill("textarea[aria-label='Problem']", "Cart abandonment")
            page.fill("textarea[aria-label='Solution']", "2-step flow")
            page.fill("textarea[aria-label='Result']", "12% recovered")
            shots.append(shot(page, "10_case_study_filled"))
            page.click("button:has-text('Save case study')")
            page.wait_for_load_state("networkidle")

            # ══ PROPOSALS: copy-proposal button + submit form ═════
            pass_gate(sprint_id, "B")
            page_label["v"] = "proposals"
            page.goto(f"{BASE}/sprints/{sprint_id}/proposals")
            page.wait_for_selector("text=First-Bid")
            content = page.content()
            check(page, "copy-proposal button wired", "data-copy-proposal" in content)
            check(page, "proposal-text payload present", "proposal-text" in content)
            shots.append(shot(page, "11_proposals"))

            # ══ MENTOR: form path ═════════════════════════════════
            page_label["v"] = "mentor"
            page.goto(f"{BASE}/mentor")
            page.wait_for_selector("text=AI Mentor")
            page.fill("input[name=question]", "Where do I start?")
            shots.append(shot(page, "12_mentor_filled"))
            page.click("button[type=submit]")
            page.wait_for_load_state("networkidle")
            check(page, "mentor answer rendered", "Mentor" in page.content())

            video_path = page.video.path() if page.video else None
            context.close()
            browser.close()

        cleanup(sprint_id)
        print("\n══ UI INTERACTION VISUAL SUMMARY ══")
        print(f"screenshots: {len(shots)} in {OUT}/shots/")
        print(f"video: {video_path}")
        print(f"console errors: {len(console_errors)}")
        for label, typ, text in console_errors:
            print(f"  [{label}] {typ}: {text}")
        print("RESULT: " + ("PASS ✅" if not console_errors else "FAIL ❌"))
    finally:
        server.terminate()
        server.wait(timeout=10)


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


def cleanup(sprint_id):
    sb = _sb()
    sb.table("sprints").delete().eq("id", sprint_id).execute()
    print("  🧹 visual-run sprint cleaned up")


if __name__ == "__main__":
    run()
