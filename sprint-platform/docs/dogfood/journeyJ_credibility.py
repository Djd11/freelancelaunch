"""Journey J — the credibility-killer tests.

A brand-new account tries to shortcut the whole product in under a minute:
enroll -> click 'Complete sprint' -> ask for a badge -> show up in the client
filter. Also: Gate B with no case study, request-a-sprint, and mobile layout.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "journeyJ")
from harness import Dogfood, BASE, ART

d = Dogfood()
R = {"steps": []}


def rec(name, **kw):
    R["steps"].append(dict(name=name, **kw))
    print(f"  > {name}: " + json.dumps(kw, default=str)[:600], flush=True)


# ------------------------------------------------ zero-work completion attempt
d.step("J1", "Fresh account, enroll, and immediately click 'Complete sprint'")
email = f"dogfood.shortcut{int(time.time())}@example.com"
d.goto(f"{BASE}/auth/signup")
d.page.fill("#display_name", "Shortcut Test")
d.page.fill("#email", email)
d.page.click('button[type=submit]')
d.page.wait_for_load_state("domcontentloaded", timeout=40000)
d.goto(f"{BASE}/sprints")
d.page.locator('form[action$="/web-scraping/start"] button').first.click()
d.page.wait_for_load_state("domcontentloaded", timeout=60000)
sid2 = d.page.url.rstrip("/").split("/")[-1]
rec("enrolled", sprint=sid2, url=d.page.url.replace(BASE, ""))

btn = d.page.locator('button:has-text("Complete sprint"), a:has-text("Complete sprint")')
rec("complete-sprint button on day 1", present=btn.count() > 0)
if btn.count():
    btn.first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(1500)
    body = d.text()
    rec("after clicking Complete sprint", status=d.page.url.replace(BASE, ""),
        lines=[l.strip() for l in body.splitlines() if "complet" in l.lower() or "badge" in l.lower()][:8])
    d.shot("J1-after-complete-click")

d.step("J2", "Ask for the Demand-Validated badge on a zero-work sprint")
st = d.goto(f"{BASE}/sprints/{sid2}/badge")
body = d.text()
rec("badge endpoint", status=st, badge_text=[l.strip() for l in body.splitlines()
                                             if "badge" in l.lower()][:6])
d.shot("J2-badge-endpoint")

d.step("J3", "Does the zero-work sprint show up as verified supply for clients?")
b, anon = d.fresh_incognito()
pg = anon.new_page()
pg.goto(f"{BASE}/clients/freelancers", wait_until="domcontentloaded")
rec("clients filter", text=pg.inner_text("body")[:400].replace("\n", " | "))
pg.goto(f"{BASE}/profile/shortcut-test", wait_until="domcontentloaded")
rec("shortcut profile", url=pg.url.replace(BASE, ""),
    text=pg.inner_text("body")[:400].replace("\n", " | "))
pg.screenshot(path=str(ART.parent / "shots" / "J3-shortcut-profile.png"), full_page=True)
b.close()

d.step("J4", "Sprint record after the shortcut")
d.goto(f"{BASE}/sprints/{sid2}")
body = d.text()
rec("dashboard state", status_line=[l.strip() for l in body.splitlines()[:16]],
    completed_words=[w for w in ["COMPLETED", "completed", "Badge issued", "verified"] if w in body])
d.shot("J4-dashboard-after-shortcut")

# ------------------------------------------------ Gate B with no real work
d.step("J5", "Gate B: submit the Mock Contract with no case study (on the main sprint)")
sid = open(ART / "sprint_id.txt").read().strip()
d.goto(f"{BASE}/sprints/{sid}/contract")
btn = d.page.locator('button:has-text("Submit deliverable")')
rec("submit btn", n=btn.count())
if btn.count():
    btn.first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(1500)
    rec("after gate B submit", flash=d.page.locator(".flash").inner_text().strip()[:250]
        if d.page.locator(".flash").count() else "", url=d.page.url.replace(BASE, ""))
    d.shot("J5-after-contract-submit")
    body = d.text()
    rec("gate B state", lines=[l.strip() for l in body.splitlines() if "GATE" in l or "verif" in l.lower()][:8])

# ------------------------------------------------ request a sprint
d.step("J6", "Request a sprint that doesn't exist")
d.goto(f"{BASE}/sprints")
inp = d.page.locator('form[action="/sprints/request"] input[type=text], form[action="/sprints/request"] input').first
if inp.count():
    inp.fill("Shopify Apps")
    d.page.locator('form[action="/sprints/request"] button').first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=30000)
    rec("requested", url=d.page.url.replace(BASE, ""), flash=d.page.locator(".flash").inner_text().strip()[:200]
        if d.page.locator(".flash").count() else "(no confirmation message)")
    d.shot("J6-after-request")
    body = d.text()
    rec("requested sprint visible?", present="Shopify Apps" in body or "shopify-apps" in body)
    rec("requested sprint startable?", present=bool(d.page.locator('form[action$="/shopify-apps/start"]').count()))

# ------------------------------------------------ mobile layout
d.step("J7", "Mobile viewport (390x844) — freelancers live on phones")
d.ctx.close()
ctx = d.browser.new_context(viewport={"width": 390, "height": 844}, storage_state=str(ART / "state.json"))
mp = ctx.new_page()
for path, tag in [("/", "landing"), (f"/sprints/{sid}", "dashboard"), (f"/sprints/{sid}/day/3", "day3")]:
    mp.goto(BASE + path, wait_until="domcontentloaded")
    mp.wait_for_timeout(1200)
    metrics = mp.evaluate("""() => ({
        docW: document.documentElement.scrollWidth,
        winW: window.innerWidth,
        overflow: document.documentElement.scrollWidth - window.innerWidth,
        tiny: [...document.querySelectorAll('button,a,input')].filter(e => {
            const r = e.getBoundingClientRect();
            return r.width > 0 && (r.height < 32 || r.width < 32);
        }).length,
        clipped: [...document.querySelectorAll('h1,h2,p,button,.btn')].filter(e => {
            const s = getComputedStyle(e);
            return s.overflow === 'hidden' && e.scrollHeight > e.clientHeight + 4;
        }).length
    })""")
    rec(f"mobile {tag}", **metrics)
    mp.screenshot(path=str(ART.parent / f"shots/J7-mobile-{tag}.png"), full_page=True)
ctx.close()

(ART / "journeyJ.json").write_text(json.dumps(R, indent=1))
print("\nERRORS:", json.dumps(d.errors()[:12], indent=1))
d.close()
print("Journey J done")
