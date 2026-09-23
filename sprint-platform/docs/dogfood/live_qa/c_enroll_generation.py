"""Phase C: enroll in Email Automation + watch content generation on Render.
Polls /generation JSON every 10s for up to 6 min; also checks whether the
dashboard banner updates WITHOUT a reload (auto-poll truthfulness).
Records: 500s, partial states, completion time, first-lesson-readable time."""
import json, re, sys, time
from playwright.sync_api import sync_playwright

BASE = "https://freelancelaunch.onrender.com"
STATE = "docs/dogfood/live_qa/state_ravi.json"
CLUSTER = sys.argv[1] if len(sys.argv) > 1 else "email-automation"

out = {"polls": [], "console_errors": [], "bad_responses": [], "notes": []}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900}, storage_state=STATE)
    page = ctx.new_page()
    page.on("console", lambda m: out["console_errors"].append({"url": page.url, "text": m.text}) if m.type == "error" else None)
    page.on("response", lambda r: out["bad_responses"].append({"url": r.url, "status": r.status, "page": page.url}) if r.status >= 400 else None)

    # enroll via the picker button (real click, real POST)
    t0 = time.time()
    page.goto(BASE + "/sprints", wait_until="domcontentloaded", timeout=90000)
    # find the card for CLUSTER and click its Start sprint button
    form_sel = f'form[action="/sprints/{CLUSTER}/start"]'
    page.wait_for_selector(form_sel, timeout=30000)
    page.click(form_sel + " button")
    page.wait_for_load_state("domcontentloaded", timeout=90000)
    enroll_dt = time.time() - t0
    out["enroll_to_dashboard_s"] = round(enroll_dt, 2)
    out["dashboard_url"] = page.url
    sprint_id = page.url.rstrip("/").split("/")[-1]
    out["sprint_id"] = sprint_id
    # dashboard right after enroll
    out["dashboard_text_at_enroll"] = page.inner_text("body")[:2500]

    # watch WITHOUT reloading for 6 min: banner text + /generation JSON every 10s
    t_start = time.time()
    last_banner = None
    ready_at = None
    while time.time() - t_start < 360:
        time.sleep(10)
        el = time.time() - t_start
        try:
            r = ctx.request.get(f"{BASE}/sprints/{sprint_id}/generation", timeout=90000)
            j = r.json() if r.status == 200 else {"http": r.status, "body": r.text()[:200]}
        except Exception as e:
            j = {"exception": str(e)}
        # banner as rendered on the still-open page (no reload)
        try:
            banner = page.eval_on_selector(
                "#gen-banner",
                "e => (e.offsetParent !== null ? 'VISIBLE: ' : 'hidden: ') + e.innerText.replace(/\\s+/g,' ').trim()") if page.is_closed() is False else None
        except Exception:
            banner = None
        rec = {"t_s": round(el, 1), "gen": j, "banner_live_page": banner}
        out["polls"].append(rec)
        if banner != last_banner:
            out["notes"].append(f"t={el:.0f}s banner changed (no reload): {str(banner)[:120]}")
            last_banner = banner
        if isinstance(j, dict) and j.get("status") == "ready":
            ready_at = el
            break
    out["generation_ready_after_s"] = round(ready_at, 1) if ready_at else None

    # after ready: reload dashboard, capture day cards
    page.goto(BASE + f"/sprints/{sprint_id}", wait_until="domcontentloaded", timeout=90000)
    out["dashboard_text_after"] = page.inner_text("body")[:4000]
    # uuids visible in html?
    html = page.content()
    out["uuids_in_dashboard_html"] = sorted(set(re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", html)))[:5]
    # open day 1
    t_day = time.time()
    page.goto(BASE + f"/sprints/{sprint_id}/day/1", wait_until="domcontentloaded", timeout=90000)
    out["day1_url"] = page.url
    out["day1_load_s"] = round(time.time() - t_day, 2)
    out["day1_text_head"] = page.inner_text("body")[:3000]
    ctx.storage_state(path=STATE)
    browser.close()
print(json.dumps(out, indent=1))
