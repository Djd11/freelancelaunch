"""Journey H — client loop, mentor network behaviour, second account (IDOR + slug
collision), CSRF, and responsive/layout health.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "journeyH")
from harness import Dogfood, BASE, ART

sid = open(ART / "sprint_id.txt").read().strip()
d = Dogfood()
R = {"steps": []}


def rec(name, **kw):
    R["steps"].append(dict(name=name, **kw))
    print(f"  > {name}: " + json.dumps(kw, default=str)[:700], flush=True)


# ------------------------------------------------ mentor: what does the network say?
d.step("H1", "Mentor turn — capture the actual HTTP exchange")
d.goto(f"{BASE}/mentor")
msgs_before = len(d.page.locator("body").inner_text())
try:
    d.page.locator("textarea, input[type=text]").first.fill("How should I price my first Klaviyo job?")
except Exception as e:
    rec("fill error", err=str(e)[:150])
resp_box = {}


def on_resp(r):
    if "/mentor/turn" in r.url:
        try:
            resp_box["status"] = r.status
            resp_box["body"] = r.text()[:600]
        except Exception as e:
            resp_box["err"] = str(e)[:150]


d.page.on("response", on_resp)
t = time.time()
d.page.locator('button:has-text("Send")').first.click(timeout=8000)
for _ in range(40):
    d.page.wait_for_timeout(2000)
    if resp_box:
        break
rec("mentor turn", secs=round(time.time() - t, 1), **resp_box)
d.page.wait_for_timeout(1500)
d.shot("H1-mentor-after")
after = d.page.locator("body").inner_text()
rec("mentor ui changed", delta=len(after) - msgs_before,
    tail=after[-500:].replace("\n", " | "))

# ------------------------------------------------ public profile / client loop
d.step("H2", "Public profile as an anonymous client would see it")
b, anon = d.fresh_incognito()
pg = anon.new_page()
r = pg.goto(f"{BASE}/profile/dana", wait_until="domcontentloaded")
rec("anon /profile/dana", status=r.status, headline=[l for l in pg.inner_text("body").splitlines() if l.strip()][:12])
pg.screenshot(path=str(ART.parent / "shots" / "H2-profile-anon.png"), full_page=True)
r = pg.goto(f"{BASE}/clients/freelancers", wait_until="domcontentloaded")
txt = pg.inner_text("body")
rec("clients filter", status=r.status, text=txt[:700].replace("\n", " | "))
pg.screenshot(path=str(ART.parent / "shots" / "H2b-clients-filter.png"), full_page=True)
# try the actual filter
try:
    inp = pg.locator("input[name=badge], input[name=q], input[type=search], input").first
    inp.fill("email-automation")
    pg.locator("button:has-text('Filter'), button:has-text('Search'), button[type=submit]").first.click(timeout=5000)
    pg.wait_for_load_state("domcontentloaded", timeout=20000)
    rec("clients filter searched", text=pg.inner_text("body")[:500].replace("\n", " | "))
    pg.screenshot(path=str(ART.parent / "shots" / "H2c-clients-filter-results.png"), full_page=True)
except Exception as e:
    rec("clients filter error", err=str(e)[:200])
b.close()

# ------------------------------------------------ second account: IDOR + slug collision
d.step("H3", "Second account with the SAME first name (slug collision + cross-user access)")
b2, ctx2 = d.fresh_incognito()
p2 = ctx2.new_page()
p2.goto(f"{BASE}/auth/signup", wait_until="domcontentloaded")
p2.fill("#display_name", "Dana")
p2.fill("#email", f"dogfood.b{int(time.time())}@example.com")
p2.click('button[type=submit]')
p2.wait_for_load_state("domcontentloaded", timeout=40000)
rec("account B signed up", url=p2.url.replace(BASE, ""))
r = p2.goto(f"{BASE}/sprints/{sid}", wait_until="domcontentloaded")
body = p2.inner_text("body")
rec("IDOR: account B opens account A's sprint", status=r.status,
    leaked=("Email Automation Sprint" in body and "Job Unlock Meter" in body),
    blocked=("not found" in body.lower() or "SITE ERROR" in body or "Sign in" in body),
    first=[l for l in body.splitlines() if l.strip()][:8])
p2.screenshot(path=str(ART.parent / "shots" / "H3-idor.png"), full_page=True)
r = p2.goto(f"{BASE}/sprints/{sid}/day/3", wait_until="domcontentloaded")
rec("IDOR day view", status=r.status, leaked="Rebuild" in p2.inner_text("body"))
r = p2.goto(f"{BASE}/profile/me", wait_until="domcontentloaded")
rec("account B own profile slug", url=p2.url.replace(BASE, ""), status=r.status)
b2.close()

# ------------------------------------------------ CSRF + method abuse
d.step("H4", "CSRF and method abuse")
cookie = d.ctx.cookies()[0]["value"]
import urllib.request, urllib.error


def post(path, data, send_csrf=True):
    body = urllib.parse.urlencode(data).encode()
    if send_csrf:
        body = urllib.parse.urlencode({**data, "csrf_token": d.page.evaluate(
            "()=>{const i=document.querySelector('input[name=csrf_token]');return i?i.value:''}")}).encode()
    req = urllib.request.Request(BASE + path, data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded",
                                          "Cookie": f"session={cookie}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


d.goto(f"{BASE}/sprints/{sid}")
tok = d.page.evaluate("()=>{const i=document.querySelector('input[name=csrf_token]');return i?i.value:null}")
rec("csrf token present in page", present=bool(tok))
st, info = post(f"/sprints/{sid}/day/2/complete", {}, send_csrf=False)
rec("POST without csrf token", status=st, info=str(info)[:160])
st, info = post("/sprints/email-automation/start", {}, send_csrf=False)
rec("enroll POST without csrf", status=st, info=str(info)[:160])

d.step("H5", "Layout health at 3 viewports (mobile-first audience)")
d.close()

print("\nERRORS:", json.dumps(R, indent=1)[:1])
(ART / "journeyH.json").write_text(json.dumps(R, indent=1))
