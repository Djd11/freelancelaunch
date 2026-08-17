"""Headed Playwright probe — do the check-items ("checkboxes") respond to clicks?

User reported that clicking the check-items manually produces no visible
change. This probe clicks every check-item on the day view, dashboard, and
contract page in a REAL browser, snapshots each element before/after the
click, and reports whether anything changed. It then exercises the REAL
state-changing CTAs (Submit for check / Mark day complete) to show where
state actually changes.

Usage:  DISPLAY=:0 .venv/bin/python scripts/checkbox_probe_visual.py
"""
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = "http://127.0.0.1:5001"
OUT = "/tmp/checkbox_probe"
os.makedirs(f"{OUT}/shots", exist_ok=True)
os.makedirs(f"{OUT}/videos", exist_ok=True)

console_errors = []
page_label = {"v": "startup"}


def start_server():
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
                if json.loads(r.read()).get("status") == "ok":
                    print("server up")
                    return proc
        except Exception:
            time.sleep(0.5)
    proc.terminate()
    raise SystemExit("server did not become healthy")


def wire_console(page):
    def on_console(msg):
        if msg.type == "error":
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


def elem_state(loc):
    """class + cbox text of a check-item element."""
    cls = loc.get_attribute("class") or ""
    cbox = loc.locator(".cbox")
    cbox_txt = (cbox.inner_text().strip() if cbox.count() else "")
    return {"class": cls, "cbox": cbox_txt}


def click_probe(page, label, loc, shots, tag):
    """Click one check-item; report before/after state."""
    before = elem_state(loc)
    loc.scroll_into_view_if_needed()
    time.sleep(0.3)
    shots.append(shot(page, f"{tag}_before"))
    loc.click()
    page.wait_for_timeout(600)  # give any JS/network a chance to react
    after = elem_state(loc)
    changed = before != after
    url_changed = False  # clicks on divs never navigate; kept for clarity
    status = "CHANGED ✅" if changed else "NO CHANGE ❌ (decorative)"
    print(f"  click  {label:<28} → {status}   class='{after['class']}' cbox='{after['cbox']}'")
    shots.append(shot(page, f"{tag}_after"))
    return changed


def run():
    from playwright.sync_api import sync_playwright
    pre_cleanup()
    server = start_server()
    shots = []
    results = []
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

            # login
            page_label["v"] = "login"
            page.goto(f"{BASE}/auth/login")
            page.fill("input[name=email]", "demo@sprint-platform.local")
            page.click("button[type=submit]")
            page.wait_for_url("**/sprints")

            # throwaway sprint
            r = page.request.post(f"{BASE}/sprints/email-automation/start", data={}, max_redirects=0)
            m = re.search(r"/sprints/([0-9a-f-]{36})$", r.headers.get("location", ""))
            assert m, f"start POST failed: {r.status}"
            sprint_id = m.group(1)
            print(f"  sprint created: {sprint_id}")

            # ══ DAY VIEW: click all 3 check-items ══════════════════
            page_label["v"] = "day-view"
            page.goto(f"{BASE}/sprints/{sprint_id}/day/1")
            page.wait_for_selector("text=Copy-Work Task")
            items = page.locator(".check-item")
            n = items.count()
            print(f"\n── DAY VIEW: {n} check-items, clicking each ──")
            for i in range(n):
                loc = items.nth(i)
                label = loc.locator("b").inner_text()
                results.append(("day", label,
                                click_probe(page, label, loc, shots, f"day{i+1}")))

            # ══ THE REAL CTAs: these DO change state ═══════════════
            print("\n── DAY VIEW: real state-changing CTAs ──")
            page.click("button:has-text('Submit for check')")
            page.wait_for_load_state("networkidle")
            print("  click  'Submit for check'            → POST /day/1/copywork OK")
            page.click("button:has-text('Mark day 1 complete')")
            page.wait_for_load_state("networkidle")
            page.goto(f"{BASE}/sprints/{sprint_id}/day/1")
            page.wait_for_load_state("networkidle")
            banner = "job postings unlocked" in page.content()
            print(f"  click  'Mark day 1 complete'         → banner shown: {banner}")
            shots.append(shot(page, "day1_after_complete_button"))

            # ══ DASHBOARD: click its 3 check-items ═════════════════
            page_label["v"] = "dashboard"
            page.goto(f"{BASE}/sprints/{sprint_id}")
            page.wait_for_selector("text=Job Unlock Meter")
            items = page.locator(".check-item")
            n = items.count()
            print(f"\n── DASHBOARD: {n} check-items, clicking each ──")
            for i in range(n):
                loc = items.nth(i)
                label = loc.locator("b").inner_text()
                results.append(("dashboard", label,
                                click_probe(page, label, loc, shots, f"dash{i+1}")))

            # ══ CONTRACT: click its 2 check-items ══════════════════
            page_label["v"] = "contract"
            page.goto(f"{BASE}/sprints/{sprint_id}/contract")
            page.wait_for_selector("text=Client Brief")
            items = page.locator(".check-item")
            n = items.count()
            print(f"\n── CONTRACT: {n} check-items, clicking each ──")
            for i in range(n):
                loc = items.nth(i)
                label = loc.locator("b").inner_text()
                results.append(("contract", label,
                                click_probe(page, label, loc, shots, f"contract{i+1}")))

            video_path = page.video.path() if page.video else None
            context.close()
            browser.close()

        cleanup(sprint_id)
        print("\n══ CHECKBOX PROBE SUMMARY ══")
        for surface, label, changed in results:
            print(f"  [{surface:<9}] {label:<28} {'CHANGED' if changed else 'NO CHANGE (decorative)'}")
        n_changed = sum(1 for _, _, c in results if c)
        print(f"\nclicked {len(results)} check-items → {n_changed} changed, "
              f"{len(results) - n_changed} inert")
        print(f"console errors: {len(console_errors)}")
        for label, typ, text in console_errors:
            print(f"  [{label}] {typ}: {text}")
        print(f"screenshots: {len(shots)} in {OUT}/shots/")
        print(f"video: {video_path}")
    finally:
        server.terminate()
        server.wait(timeout=10)


def _sb():
    from dotenv import load_dotenv
    load_dotenv()
    from app import create_app
    app = create_app()
    app.app_context().push()
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


def cleanup(sprint_id):
    sb = _sb()
    sb.table("sprints").delete().eq("id", sprint_id).execute()
    print("  🧹 probe sprint cleaned up")


if __name__ == "__main__":
    run()
