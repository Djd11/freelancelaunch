"""Reproduction #2 of generation failure via the USER recovery path:
click 'Retry generation' on the dashboard, poll /generation for 150s."""
import json, time, sys
from playwright.sync_api import sync_playwright

BASE = "https://freelancelaunch.onrender.com"
SID = sys.argv[1]
out = {"polls": [], "bad": []}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900}, storage_state="docs/dogfood/live_qa/state_ravi.json")
    page = ctx.new_page()
    page.on("response", lambda r: out["bad"].append({"url": r.url, "status": r.status}) if r.status >= 400 else None)
    page.goto(BASE + f"/sprints/{SID}", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(6000)  # let the single initial poll() fetch land
    btn = page.query_selector("#gen-retry")
    out["retry_button_visible"] = btn is not None and btn.is_visible()
    out["banner_text"] = page.eval_on_selector("#gen-banner", "e => e.innerText.replace(/\\s+/g,' ').trim()[:400]")
    if out["retry_button_visible"]:
        btn.click()
        t0 = time.time()
        for i in range(15):
            time.sleep(10)
            r = ctx.request.get(f"{BASE}/sprints/{SID}/generation", timeout=90000)
            j = r.json()
            out["polls"].append({"t": round(time.time() - t0, 1), "status": j.get("status"),
                                 "generated": j.get("generated"), "failed_days": len(j.get("failed_days") or []),
                                 "error": str(j.get("error"))[:120]})
            if j.get("status") == "partial" and i > 2:
                break
        page.reload(wait_until="domcontentloaded", timeout=90000)
        out["banner_after"] = page.eval_on_selector("#gen-banner", "e => e.innerText.replace(/\\s+/g,' ').trim()[:300]")
    browser.close()
print(json.dumps(out, indent=1))
