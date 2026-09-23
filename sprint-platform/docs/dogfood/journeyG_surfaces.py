"""Journey G — consequences of the state we're in, plus the remaining surfaces.

Covers: gate-bypass UI, Day 1 500 reproducibility, contract, proposals, mentor,
public profile, client filter, badge, logout/login round-trip.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "journeyG")
from harness import Dogfood, BASE, ART

sid = open(ART / "sprint_id.txt").read().strip()
d = Dogfood()
R = {"steps": []}


def rec(name, **kw):
    R["steps"].append(dict(name=name, **kw))
    print(f"  > {name}: " + json.dumps(kw, default=str)[:700], flush=True)


def page_summary(tag, path, shot=None):
    st = d.goto(path)
    body = d.text()
    rec(tag, status=st, url=d.page.url.replace(BASE, ""), chars=len(body),
        h1=[l.strip() for l in body.splitlines()[:14]],
        error="SITE ERROR" in body or "500" == body.strip()[:3])
    if shot:
        d.shot(shot)
    return body


d.step("G1", "Dashboard now: Phase A done-ish, Gate A pending — what does the learner see?")
body = page_summary("dashboard", f"{BASE}/sprints/{sid}", "G1-dashboard-now")
print(body[:2600])
rec("phase labels", shiftB=[l for l in body.splitlines() if "LOCKED" in l or "IN PROGRESS" in l][:8])
rec("gate copy", unlock_lines=[l.strip() for l in body.splitlines() if "Unlocks" in l or "verif" in l.lower()][:6])

d.step("G2", "Day 1 again — is the 500 reproducible?")
for i in range(3):
    st = d.goto(f"{BASE}/sprints/{sid}/day/1")
    body = d.text()
    rec(f"day1 load {i+1}", status=st, site_error="SITE ERROR" in body, first=[l for l in body.splitlines()[:3]])
d.shot("G2-day1-recheck")

d.step("G3", "Phase B surfaces (contract + case study)")
body = page_summary("contract", f"{BASE}/sprints/{sid}/contract", "G3-contract")
print(body[:1800])

d.step("G4", "Phase C surface (proposals) — should be locked")
body = page_summary("proposals", f"{BASE}/sprints/{sid}/proposals", "G4-proposals")
print(body[:1800])

d.step("G5", "AI Mentor")
d.goto(f"{BASE}/mentor")
d.shot("G5-mentor-empty")
print("  --- mentor page ---")
print(d.text()[:1200])
box = d.page.locator("textarea, input[type=text]").first
if box.count() if hasattr(box, "count") else True:
    try:
        box.fill("How do I price my first Klaviyo job?")
        t = time.time()
        d.page.locator('button:has-text("Send"), button:has-text("Ask")').first.click(timeout=8000)
        d.page.wait_for_timeout(1000)
        # mentor replies via fetch; wait for a reply to appear
        for _ in range(24):
            d.page.wait_for_timeout(2500)
            txt = d.text()
            if "How do I price" in txt and txt.count("How do I price") >= 1 and len(txt) > 900:
                break
        rec("mentor reply", ms=round((time.time() - t) * 1000), len=len(d.text()))
        d.shot("G5b-mentor-after-ask")
        print("  --- mentor after ask ---")
        print(d.text()[:2500])
    except Exception as e:
        rec("mentor error", err=str(e)[:250])

d.step("G6", "Public profile + client filter")
body = page_summary("profile-me", f"{BASE}/profile/me", "G6-profile-me")
print(body[:1500])
slug = d.page.url.rstrip("/").split("/")[-1]
rec("profile slug", slug=slug)
b, anon = d.fresh_incognito()
pg = anon.new_page()
pg.goto(f"{BASE}/profile/{slug}", wait_until="domcontentloaded")
rec("anon profile", status=pg.status, title=pg.title())
pg.screenshot(path=str(ART.parent / "shots" / "G6b-profile-anon.png"), full_page=True)
rec("anon profile text", text=pg.inner_text("body")[:600].replace("\n", " | "))
pg.goto(f"{BASE}/clients/freelancers", wait_until="domcontentloaded")
rec("clients filter", status=pg.status, text=pg.inner_text("body")[:500].replace("\n", " | "))
pg.screenshot(path=str(ART.parent / "shots" / "G6c-clients-filter.png"), full_page=True)
b.close()

d.step("G7", "Badge endpoint")
page_summary("badge", f"{BASE}/sprints/{sid}/badge", "G7-badge")

d.step("G8", "Sign out, then sign back in with the same email")
d.goto(f"{BASE}/auth/logout")
rec("after logout", url=d.page.url.replace(BASE, ""))
d.goto(f"{BASE}/auth/login")
email = json.load(open(ART / "journeyB.json"))["email"]
d.page.fill("#email", email)
d.page.click('button[type=submit]')
d.page.wait_for_load_state("domcontentloaded", timeout=30000)
rec("relogin", url=d.page.url.replace(BASE, ""), ok="/sprints" in d.page.url)
d.shot("G8-after-relogin")

(ART / "journeyG.json").write_text(json.dumps(R, indent=1))
print("\nERRORS:", json.dumps(d.errors()[:20], indent=1))
d.close()
print("Journey G done")
