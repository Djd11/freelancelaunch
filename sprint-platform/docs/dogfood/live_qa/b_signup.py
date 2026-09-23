"""Phase B: first-run signup as Ravi. Saves storage_state for later phases.
Measures: time from landing on /auth/signup to logged-in picker; what the
user sees immediately after signup (is anything explained?)."""
import json, sys, time
from playwright.sync_api import sync_playwright

BASE = "https://freelancelaunch.onrender.com"
EMAIL = sys.argv[1]
NAME = sys.argv[2]
STATE = sys.argv[3]

out = {}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    errs, bad = [], []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.on("response", lambda r: bad.append({"url": r.url, "status": r.status}) if r.status >= 400 else None)

    t0 = time.time()
    page.goto(BASE + "/auth/signup", wait_until="domcontentloaded", timeout=90000)
    out["signup_page_load_s"] = round(time.time() - t0, 2)
    out["signup_form_fields"] = page.eval_on_selector_all(
        "input,select,textarea",
        "els => els.map(e => ({name: e.name, type: e.type, placeholder: e.placeholder, required: e.required}))")
    out["signup_page_text"] = page.inner_text("body")[:2500]

    t1 = time.time()
    page.fill("input[name=display_name]", NAME)
    page.fill("input[name=email]", EMAIL)
    page.click("button[type=submit]")
    page.wait_for_load_state("domcontentloaded", timeout=90000)
    out["signup_submit_to_land_s"] = round(time.time() - t1, 2)
    out["post_signup_url"] = page.url
    out["post_signup_text"] = page.inner_text("body")[:5000]
    out["post_signup_flash"] = page.eval_on_selector_all(
        ".flash, .flash-message, [class*=flash], [class*=alert]",
        "els => els.map(e => e.innerText.trim())")
    ctx.storage_state(path=STATE)
    out["console_errors"] = errs
    out["bad_responses"] = bad
    browser.close()
print(json.dumps(out, indent=1))
