"""Journey B — first-time signup, pick a sprint, enroll, watch the first-run dashboard.

Plays a nervous first-time freelancer: creates an account, chooses the most
in-demand skill, and sees what the product does with them in the first 60 seconds.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "journeyB")
from harness import Dogfood, BASE, ART, STATE_FILE

EMAIL = os.environ.get("DOGFOOD_EMAIL")
NAME = os.environ.get("DOGFOOD_NAME", "Dana")
CLUSTER = os.environ.get("DOGFOOD_CLUSTER", "email-automation")

d = Dogfood()
findings = []


def check(name, ok, detail=""):
    findings.append({"check": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(("  PASS " if ok else "  FAIL ") + name + (f" — {str(detail)[:300]}" if detail else ""))


# ------------------------------------------------------------------ signup
d.step("B1", "Create a free account (email + first name only)")
d.goto("/auth/signup")
d.shot("B1-signup-form", full=False)
print("  forms:", json.dumps(d.forms(), indent=1)[:900])

EMAIL = EMAIL or f"dogfood.{int(time.time())}@example.com"
d.fill_guard = None
d.page.fill("#display_name", NAME)
d.page.fill("#email", EMAIL)
d.shot("B2-signup-filled", full=False)
t = time.time()
d.page.click('button[type=submit]')
d.page.wait_for_load_state("domcontentloaded", timeout=45000)
signup_ms = round((time.time() - t) * 1000)
print(f"  signed up as {EMAIL} in {signup_ms}ms -> {d.page.url}")
check("signup lands in the product (not an error page)", "/sprints" in d.page.url, d.page.url)
check("welcome message shown", "Welcome" in d.text() or "Pick a skill" in d.text(), d.text()[:120])
d.shot("B3-after-signup", full=False)

# ------------------------------------------------------------------ picker
d.step("B2", "Sprint picker as a logged-in newcomer")
body = d.text()
d.shot("B4-picker-logged-in")
check("picker lists sprint cards", "jobs open" in body)
check("cards have a real Start action", d.page.locator("form button, button").count() > 0)
print("  forms:", json.dumps(d.forms(), indent=1)[:1200])

# ------------------------------------------------------------------ enroll
d.step("B3", f"Start the '{CLUSTER}' sprint")
before = time.time()
started = False
for sel in [f'form[action$="/{CLUSTER}/start"] button',
            f'button:text("Start sprint")',
            f'a[href$="/{CLUSTER}/start"]']:
    try:
        loc = d.page.locator(sel)
        if loc.count():
            loc.first.click()
            started = True
            print(f"  clicked {sel}")
            break
    except Exception as e:
        print(f"  ({sel} not clickable: {e})")
if not started:
    # fall back to a direct POST-equivalent navigation via the form
    d.page.evaluate("""(k)=>{const f=document.querySelector(`form[action$="${k}/start"]`); if(f) f.submit();}""", CLUSTER)
d.page.wait_for_load_state("domcontentloaded", timeout=60000)
enroll_ms = round((time.time() - before) * 1000)
print(f"  enrolled in {enroll_ms}ms -> {d.page.url}")
check("enroll round-trip under 3s", enroll_ms < 3000, f"{enroll_ms}ms")
sprint_url = d.page.url
sprint_id = sprint_url.rstrip("/").split("/")[-1]
check("landed on a sprint dashboard", "/sprints/" in sprint_url and len(sprint_id) > 20, sprint_url)

# ------------------------------------------------------------------ first-run dashboard
d.step("B4", "The very first dashboard a new user sees (content still generating)")
d.shot("B5-dashboard-t0")
dash0 = d.text()
print("  --- dashboard at t0 (first 2500 chars) ---")
print(dash0[:2500])

# poll the generation surface the way the real page does
d.step("B5", "Wait for async lesson generation (as a user would, staring at the screen)")
deadline = time.time() + float(os.environ.get("DOGFOOD_WAIT", "420"))
marks = []
while time.time() < deadline:
    d.goto(sprint_url)
    txt = d.text()
    m = {"t": round(time.time() - (deadline - 420)), "url": d.page.url}
    ready = ("generating" not in txt.lower()) and ("Sprint Content" in txt or "Day 1" in txt)
    m["ready"] = ready
    marks.append(m)
    if len(marks) <= 3 or ready:
        print(f"  poll t+{m['t']}s ready={ready} url={d.page.url.replace(BASE,'')}")
        d.shot(f"B6-dashboard-poll-{len(marks)}")
    if ready:
        break
    time.sleep(20)
print("  marks:", json.dumps(marks))

d.dump("B7-dashboard-after-wait", 9000)
print("  --- dashboard now (first 3000 chars) ---")
print(d.text()[:3000])

d.step("B6", "Console/network health")
for e in d.errors()[:30]:
    print("   ", e)

out = {"email": EMAIL, "name": NAME, "sprint_id": sprint_id, "sprint_url": sprint_url,
       "signup_ms": signup_ms, "enroll_ms": enroll_ms, "findings": findings,
       "timings": d.timings, "errors": d.errors()}
(ART / "journeyB.json").write_text(json.dumps(out, indent=1))
d.close()
print("\nJourney B done. sprint_id =", sprint_id, "email =", EMAIL)
