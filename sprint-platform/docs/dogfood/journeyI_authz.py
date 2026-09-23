"""Precise authorization + identity checks (no false positives).

Uses strings that exist ONLY inside account A's sprint, and checks which account
/profile a shared slug actually resolves to.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "journeyI")
from harness import Dogfood, BASE, ART

sid = open(ART / "sprint_id.txt").read().strip()
d = Dogfood()
R = {}

# A unique marker that only exists in account A's day-3 content
MARKER = "Rebuild the Checkout Welcome Flow in Klaviyo"

d.step("I1", "Account A: confirm the marker is really on A's day 3")
d.goto(f"{BASE}/sprints/{sid}/day/3")
a_body = d.text()
R["a_day3_has_marker"] = MARKER in a_body
print("  A sees marker:", R["a_day3_has_marker"])

d.step("I2", "Account B (different user) requests A's day 3")
b2, ctx2 = d.fresh_incognito()
p2 = ctx2.new_page()
p2.goto(f"{BASE}/auth/signup", wait_until="domcontentloaded")
p2.fill("#display_name", "Dana")
p2.fill("#email", f"dogfood.c{int(time.time())}@example.com")
p2.click('button[type=submit]')
p2.wait_for_load_state("domcontentloaded", timeout=40000)
p2.goto(f"{BASE}/sprints/{sid}/day/3", wait_until="domcontentloaded")
b_body = p2.inner_text("body")
R["b_landed_on"] = p2.url.replace(BASE, "")
R["b_leaked_marker"] = MARKER in b_body
R["b_sees_own_picker"] = "Choose your sprint" in b_body
print("  B landed:", R["b_landed_on"], "| leaked:", R["b_leaked_marker"], "| own picker:", R["b_sees_own_picker"])
p2.screenshot(path=str(ART.parent / "shots" / "I2-accountB-on-A-day3.png"), full_page=True)

d.step("I3", "Account B POSTs to A's day-complete endpoint (write-side authz)")
tok = p2.evaluate("()=>{const i=document.querySelector('input[name=csrf_token]');return i?i.value:null}")
import urllib.request, urllib.error, urllib.parse
cookie = ctx2.cookies()[0]["value"]
body = urllib.parse.urlencode({"csrf_token": tok or ""}).encode()
req = urllib.request.Request(f"{BASE}/sprints/{sid}/day/3/complete", data=body,
                             headers={"Content-Type": "application/x-www-form-urlencoded",
                                      "Cookie": f"session={cookie}"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        R["b_post_complete"] = {"status": r.status, "url": r.geturl().replace(BASE, "")}
except urllib.error.HTTPError as e:
    R["b_post_complete"] = {"status": e.code, "body": e.read().decode()[:150]}
print("  B POST /day/3/complete ->", R["b_post_complete"])

d.step("I4", "Did that write change account A's day 3?")
d.goto(f"{BASE}/sprints/{sid}/day/3")
R["a_day3_still_incomplete"] = ("Mark day 3 complete" in d.text())
print("  A's day 3 still incomplete:", R["a_day3_still_incomplete"])

d.step("I5", "Shared slug: whose profile is /profile/dana?")
r = p2.goto(f"{BASE}/profile/me", wait_until="domcontentloaded")
R["b_profile_url"] = p2.url.replace(BASE, "")
R["b_profile_email_hint"] = "dogfood" in p2.inner_text("body").lower()
print("  B's /profile/me ->", R["b_profile_url"])
r = p2.goto(f"{BASE}/profile/dana", wait_until="domcontentloaded")
R["slug_page"] = p2.inner_text("body")[:400].replace("\n", " | ")
print("  /profile/dana (as B):", R["slug_page"][:300])
p2.screenshot(path=str(ART.parent / "shots" / "I5-shared-slug.png"), full_page=True)
b2.close()

d.step("I6", "A's own view of the shared slug")
d.goto(f"{BASE}/profile/dana")
R["a_slug_page"] = d.text()[:400].replace("\n", " | ")
print("  /profile/dana (as A):", R["a_slug_page"][:300])

(ART / "journeyI.json").write_text(json.dumps(R, indent=1))
print("\nERRORS:", json.dumps(d.errors()[:8], indent=1))
d.close()
