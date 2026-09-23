"""Re-verify the journeyJ-era findings on the HEALTHY server (post captain's 20:43 restart).

journeyJ ran at 19:43, right as the old server process was dying, so its 500s are
suspect. This re-runs exactly those claims on a fresh account against a server that
/health reports as ok, and records the HTTP status of every step plus the DB truth.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "reverifyJ")
from harness import Dogfood, BASE, ART

d = Dogfood()
R = {"steps": []}


def rec(name, **kw):
    R["steps"].append(dict(name=name, **kw))
    print(f"  > {name}: " + json.dumps(kw, default=str)[:700], flush=True)


def shot(n):
    d.shot(n)
    print(f"    [shot] shots/{n}.png", flush=True)


d.step("RJ0", "Server sanity")
rec("health", status=d.goto("/health"), body=d.text()[:160])

d.step("RJ1", "Fresh account, enroll, Day 1 (the journeyJ scenario, healthy server)")
email = f"rejverify_{int(time.time())}@example.com"
d.goto(f"{BASE}/auth/signup")
d.page.fill("#display_name", "ReJVerify")
d.page.fill("#email", email)
d.page.click('button[type=submit]')
d.page.wait_for_load_state("domcontentloaded", timeout=45000)
d.goto(f"{BASE}/sprints")
t = time.time()
d.page.locator('form[action$="/web-scraping/start"] button').first.click()
d.page.wait_for_load_state("domcontentloaded", timeout=90000)
sid = d.page.url.rstrip("/").split("/")[-1]
(ART / "sprint_id_rj.txt").write_text(sid)
rec("enroll", ms=round((time.time() - t) * 1000), sprint=sid, email=email)

d.step("RJ2", "Click 'Complete sprint' on Day 1 — capture the POST status")
d.goto(f"{BASE}/sprints/{sid}")
btn = d.page.locator('form[action$="/complete"] button')
rec("complete btn present on day 1", n=btn.count())
statuses = []
d.page.on("response", lambda r: statuses.append((r.status, r.url.replace(BASE, "")))
          if "/complete" in r.url else None)
if btn.count():
    btn.first.click(timeout=15000)
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(2000)
    b = d.text()
    rec("POST /complete", exchanges=statuses, site_error="SITE ERROR" in b,
        claims=[l.strip() for l in b.splitlines()
                if "complete" in l.lower() or "badge" in l.lower() or "14 days" in l][:6])
    shot("80-rj-zero-work-complete")

d.step("RJ3", "Badge endpoint on the healthy server")
st = d.goto(f"{BASE}/sprints/{sid}/badge")
b = d.text()
rec("GET /badge", status=st, site_error="SITE ERROR" in b,
    text=[l.strip() for l in b.splitlines() if l.strip()][:12])
shot("81-rj-badge-endpoint")

d.step("RJ4", "Public profile of a zero-work 'completed' sprint (anonymous client view)")
b1, anon = d.fresh_incognito()
pg = anon.new_page()
r = pg.goto(f"{BASE}/profile/rejverify", wait_until="domcontentloaded")
txt = pg.inner_text("body")
rec("anon profile", status=r.status, not_found="Not found" in txt,
    claims_badge="badge" in txt.lower(), lines=[l.strip() for l in txt.splitlines() if l.strip()][:12])
pg.screenshot(path=str(ART.parent / "shots" / "82-rj-profile-anon.png"), full_page=True)
b1.close()

d.step("RJ5", "Client filter — does the zero-work 'completion' show up as verified supply?")
b2, anon2 = d.fresh_incognito()
pg2 = anon2.new_page()
r = pg2.goto(f"{BASE}/clients/freelancers", wait_until="domcontentloaded")
rec("clients filter", status=r.status, text=pg2.inner_text("body")[:300].replace("\n", " | "))
b2.close()

d.step("RJ6", "Re-check the other journeyJ-era claims on the healthy server")
# mentor latency
d.goto(f"{BASE}/mentor")
try:
    d.page.locator("textarea, input[type=text]").first.fill("What should I build first?")
    t = time.time()
    d.page.locator('button:has-text("Send")').first.click(timeout=8000)
    got = False
    for _ in range(25):
        d.page.wait_for_timeout(2000)
        if len(d.text()) > 900 and "What should I build first?" in d.text():
            got = True
            break
    rec("mentor", replied=got, secs=round(time.time() - t))
    shot("83-rj-mentor")
except Exception as e:
    rec("mentor err", err=str(e)[:150])
# generation endpoint concurrency
import urllib.request, urllib.error, concurrent.futures
cookie = d.ctx.cookies()[0]["value"]


def hit(_):
    req = urllib.request.Request(f"{BASE}/sprints/{sid}/generation", headers={"Cookie": f"session={cookie}"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return "ERR"


with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
    codes = list(ex.map(hit, range(12)))
rec("generation 12 parallel polls", codes=codes, non200=sum(1 for c in codes if c != 200))

(ART / "reverifyJ.json").write_text(json.dumps(R, indent=1))
print("\nERRORS:", json.dumps(d.errors()[:12], indent=1))
d.close()
print("RJ done")
