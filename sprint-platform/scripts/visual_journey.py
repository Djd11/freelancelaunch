"""Headed Playwright visual run — full admin + learner journey on the live test project.

Runs a real browser on DISPLAY=:0 with video + per-screen screenshots.
Creates a throwaway sprint + cluster, exercises every screen, then cleans up
so the live test project is left exactly as found.

Usage:  DISPLAY=:0 .venv/bin/python scripts/visual_journey.py
"""
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = "http://127.0.0.1:5001"
OUT = "/tmp/visual_run"
os.makedirs(f"{OUT}/shots", exist_ok=True)
os.makedirs(f"{OUT}/videos", exist_ok=True)

console_errors = []   # (page_label, type, text)
page_label = {"v": "startup"}


def start_server():
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "from app import create_app; create_app().run(host='127.0.0.1', port=5001, debug=False)"],
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

            page_label["v"] = "login"
            page.goto(f"{BASE}/auth/login")
            page.fill("input[name=email]", "demo@sprint-platform.local")
            page.click("button[type=submit]")
            page.wait_for_url("**/sprints")

            page_label["v"] = "picker"
            page.wait_for_selector("text=Choose your sprint")
            shots.append(shot(page, "09_picker"))

            page_label["v"] = "start-sprint"
            # max_redirects=0: we need the raw 302's Location (the sprint UUID)
            # — otherwise the request follows the redirect and Location is gone.
            r = page.request.post(f"{BASE}/sprints/email-automation/start", form={}, max_redirects=0)
            print(f"  start-sprint status={r.status}")
            loc = r.headers.get("location", "")
            m = re.search(r"/sprints/([0-9a-f-]{36})$", loc)
            assert m, f"no sprint UUID in start redirect: {loc!r}"
            sprint_id = m.group(1)
            sprint_url = f"{BASE}/sprints/{sprint_id}"
            print(f"  sprint created: {sprint_id}")
            page.goto(sprint_url)

            page_label["v"] = "dashboard"
            page.wait_for_selector("text=Job Unlock Meter")
            shots.append(shot(page, "10_dashboard_day1"))

            page_label["v"] = "day-view"
            page.click("a:has-text('Open Day 1')")
            page.wait_for_selector("text=Copy-Work Task")
            shots.append(shot(page, "11_day1"))

            # complete days 1–5 through the real HTTP surface (same session)
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
            page.reload()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
            shots.append(shot(page, "12_dashboard_after_days"))

            # copy-work + gate A (verification service writes the pass)
            page_label["v"] = "gate-a"
            page.request.post(f"{BASE}/sprints/{sprint_id}/day/4/copywork",
                              form={"rubric_url": "https://github.com/maya/flow"})
            pass_gate(sprint_id, "A")
            page.goto(sprint_url)
            page.wait_for_selector("text=Mock Contract")
            assert "Unlocks when Phase A passes verification" not in page.content()
            shots.append(shot(page, "13_dashboard_phase_b_unlocked"))

            page_label["v"] = "contract"
            page.goto(f"{BASE}/sprints/{sprint_id}/contract")
            page.wait_for_selector("text=Client Brief")
            shots.append(shot(page, "14_contract_brief"))
            page.fill("input[name=submission_url]", "https://dropbox.com/maya-deliverable")
            page.click("button[type=submit]")
            page.wait_for_selector("text=verification service is checking")
            shots.append(shot(page, "15_contract_submitted"))

            page_label["v"] = "gate-b"
            pass_gate(sprint_id, "B")
            page.goto(f"{BASE}/sprints/{sprint_id}/proposals")
            page.wait_for_selector("text=First-Bid")
            shots.append(shot(page, "16_proposals_unlocked"))

            page_label["v"] = "proposal-submit"
            page.click("button:has-text('Draft — submit')")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)
            shots.append(shot(page, "17_proposal_submitted"))

            # completion + badge
            page_label["v"] = "badge"
            complete_sprint(sprint_id)
            page.goto(f"{BASE}/sprints/{sprint_id}/badge")
            page.wait_for_load_state("networkidle")

            page_label["v"] = "profile"
            page.goto(f"{BASE}/profile/maya")
            page.wait_for_selector("text=Demand-Validated")
            shots.append(shot(page, "18_profile_badge"))

            page_label["v"] = "clients"
            page.goto(f"{BASE}/clients/freelancers?cluster=email-automation&within_days=30")
            page.wait_for_selector("text=Maya Chen")
            shots.append(shot(page, "19_clients_filter"))

            page_label["v"] = "mentor"
            page.goto(f"{BASE}/mentor")
            page.wait_for_selector("text=AI Mentor")
            shots.append(shot(page, "20_mentor"))

            page_label["v"] = "pricing"
            page.goto(f"{BASE}/pricing")
            page.wait_for_selector("text=Pricing comes after placement")
            shots.append(shot(page, "21_pricing"))

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
    """Idempotent re-runs: remove leftovers from any previously crashed run.

    The visual run owns exactly one sprint (the demo user's active
    email-automation sprint) and one cluster (visual-run-cluster) on the
    dedicated test project — delete both before starting.
    """
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
    """The demo user must have a verified platform to submit proposals.

    BDD per-scenario cleanup can delete these rows; restore idempotently so
    the visual run never depends on harness side effects.
    """
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
    """The verification service is an external actor — write its pass result."""
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
    """Delete the visual-run sprint (children cascade) + the admin test cluster."""
    sb = _sb()
    sb.table("sprints").delete().eq("id", sprint_id).execute()
    sb.table("job_clusters").delete().eq("cluster_key", "visual-run-cluster").execute()
    print("  🧹 visual-run sprint + cluster cleaned up")


if __name__ == "__main__":
    run()
