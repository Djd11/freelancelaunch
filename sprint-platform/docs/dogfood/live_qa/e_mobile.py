"""Phase E: mobile 390x844. Anonymous A pages + signup (2nd live_qa account) +
one day view. Measures horizontal overflow, elements wider than viewport,
tap targets < 44px, clipped text."""
import json, re, sys, time
from playwright.sync_api import sync_playwright

BASE = "https://freelancelaunch.onrender.com"
EMAIL = sys.argv[1]
STATE = "docs/dogfood/live_qa/state_mobile.json"
SID = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None

PROBE = """() => {
  const vw = window.innerWidth;
  const overflow = document.documentElement.scrollWidth > vw;
  const wide = [];
  document.querySelectorAll('body *').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.width > vw + 1 && r.height > 0 && getComputedStyle(e).position !== 'fixed') {
      wide.push({tag: e.tagName.toLowerCase(), cls: (e.className||'').toString().slice(0,40), w: Math.round(r.width), text: (e.innerText||'').slice(0,40)});
    }
  });
  const small = [];
  document.querySelectorAll('a,button,input[type=submit],input[type=checkbox],select,label.check-item,[role=button]').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.height > 0 && r.width > 0 && (r.height < 44 || r.width < 44) && getComputedStyle(e).display !== 'none') {
      small.push({tag: e.tagName.toLowerCase(), h: Math.round(r.height), w: Math.round(r.width), text: (e.innerText||e.value||'').slice(0,30)});
    }
  });
  const clipped = [];
  document.querySelectorAll('body *').forEach(e => {
    if (e.scrollWidth > e.clientWidth + 2 && ['hidden','clip'].includes(getComputedStyle(e).overflowX) && e.innerText && e.innerText.trim().length > 3) {
      clipped.push({tag: e.tagName.toLowerCase(), cls: (e.className||'').toString().slice(0,30), text: e.innerText.slice(0,50)});
    }
  });
  return {vw, scrollWidth: document.documentElement.scrollWidth, overflow, wide: wide.slice(0,12), small: small.slice(0,25), clipped: clipped.slice(0,12)};
}"""

out = {"pages": {}, "console_errors": [], "bad_responses": []}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    page.on("console", lambda m: out["console_errors"].append({"url": page.url, "text": m.text}) if m.type == "error" else None)
    page.on("response", lambda r: out["bad_responses"].append({"url": r.url, "status": r.status}) if r.status >= 400 else None)

    for name, path in [("landing", "/"), ("topics", "/topics"), ("topic_detail", "/topics/email-automation"), ("pricing", "/pricing")]:
        page.goto(BASE + path, wait_until="domcontentloaded", timeout=90000)
        time.sleep(0.8)
        out["pages"][name] = page.evaluate(PROBE)

    # signup on mobile
    t0 = time.time()
    page.goto(BASE + "/auth/signup", wait_until="domcontentloaded", timeout=90000)
    out["pages"]["signup_form"] = page.evaluate(PROBE)
    page.fill("input[name=display_name]", "Ravi M")
    page.fill("input[name=email]", EMAIL)
    # tap target of the submit button
    btn = page.query_selector("button[type=submit]")
    bb = btn.bounding_box()
    out["pages"]["signup_submit_tap"] = {"h": round(bb["height"]), "w": round(bb["width"])}
    page.click("button[type=submit]")
    page.wait_for_load_state("domcontentloaded", timeout=90000)
    out["pages"]["post_signup"] = page.evaluate(PROBE)
    out["pages"]["post_signup_url"] = page.url
    out["signup_s"] = round(time.time() - t0, 2)
    ctx.storage_state(path=STATE)

    # day view (Ravi's sprint, using Ravi state) — open a second context with ravi state
    if SID:
        ctx2 = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
                                   storage_state="docs/dogfood/live_qa/state_ravi.json")
        pg2 = ctx2.new_page()
        pg2.goto(BASE + f"/sprints/{SID}/day/1", wait_until="domcontentloaded", timeout=90000)
        time.sleep(0.8)
        out["pages"]["day1_mobile"] = pg2.evaluate(PROBE)
        pg2.goto(BASE + f"/sprints/{SID}", wait_until="domcontentloaded", timeout=90000)
        time.sleep(0.8)
        out["pages"]["dashboard_mobile"] = pg2.evaluate(PROBE)
        # hamburger / nav usable?
        out["pages"]["dashboard_mobile_nav_html"] = pg2.evaluate("""() => {
          const nav = document.querySelector('nav, header');
          return nav ? nav.innerText.replace(/\\s+/g,' ').slice(0,200) : null; }""")
    browser.close()
print(json.dumps(out, indent=1))
