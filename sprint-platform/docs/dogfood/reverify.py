"""Re-verification against the CURRENT build (post captain's fixes).

Every claim in the final report is re-checked here so nothing stale is reported.
Read-mostly; mutates only fresh dogfood accounts' own sprints.
"""
import sys, os, json, time, urllib.request, urllib.error, urllib.parse
import concurrent.futures
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "reverify")
from harness import Dogfood, BASE, ART, SHOTS

d = Dogfood()
R = {"steps": []}


def rec(name, **kw):
    R["steps"].append(dict(name=name, **kw))
    print(f"  > {name}: " + json.dumps(kw, default=str)[:700], flush=True)


def shot(n):
    d.shot(n)
    print(f"    [shot] shots/{n}.png", flush=True)


def stamps():
    return d.page.evaluate("""() => [...document.querySelectorAll('.stamp')].map(e =>
        ({label: e.innerText.trim(), lit: e.classList.contains('ok')}))""")


# ---------------------------------------------------------------- 1. fresh first run
d.step("V1", "Fresh account: signup -> enroll -> measure")
email = f"reverify_{int(time.time())}@example.com"
d.goto(f"{BASE}/auth/signup")
d.page.fill("#display_name", "Reverify")
d.page.fill("#email", email)
d.page.click('button[type=submit]')
d.page.wait_for_load_state("domcontentloaded", timeout=45000)
d.goto(f"{BASE}/sprints")
t = time.time()
d.page.locator('form[action$="/email-automation/start"] button').first.click()
d.page.wait_for_load_state("domcontentloaded", timeout=90000)
rec("enroll latency", ms=round((time.time() - t) * 1000))
sid = d.page.url.rstrip("/").split("/")[-1]
(ART / "sprint_id_v.txt").write_text(sid)
body = d.text()
rec("dashboard", cohort=[l.strip() for l in body.splitlines() if "COHORT" in l][:1],
    demand_chip=[l.strip() for l in body.splitlines() if "ACTIVE JOBS" in l or "/HR" in l][:2],
    generating="Generating your sprint content" in body,
    meter=[l.strip() for l in body.splitlines() if "of 127" in l or "unlocked" in l.lower()][:4])
shot("60-v-dashboard-fresh")

# ---------------------------------------------------------------- 2. generation health
d.step("V2", "/generation under 12 parallel polls (dashboard auto-poll reality)")
cookie = d.ctx.cookies()[0]["value"]


def hit(_):
    req = urllib.request.Request(f"{BASE}/sprints/{sid}/generation",
                                 headers={"Cookie": f"session={cookie}"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return "ERR"


with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
    codes = list(ex.map(hit, range(12)))
rec("parallel polls", codes=codes, non200=sum(1 for c in codes if c != 200))

# ---------------------------------------------------------------- 3. Day 1 reality
d.step("V3", "Day 1 — lesson, task, rubric, submit, complete")
d.goto(f"{BASE}/sprints/{sid}/day/1")
b = d.text()
rec("day1 lesson", failed="generation failed" in b.lower(), generating="Generating your lesson" in b,
    eyebrow=[l.strip() for l in b.splitlines() if "DAY 01" in l][:1],
    project_label=[l.strip() for l in b.splitlines() if "PROJECT" in l.upper()][:1])
shot("61-v-day1-lesson")
try:
    d.page.locator('button:text-is("Task")').first.click(timeout=6000)
    d.page.wait_for_timeout(700)
except Exception as e:
    rec("task tab", err=str(e)[:100])
b = d.text()
rec("day1 task", checkboxes=d.page.locator('input[type=checkbox]').count(),
    steps=d.page.locator("ol li").count(),
    copy=[l.strip() for l in b.splitlines() if "points are ticked" in l][:1],
    stamps=stamps())
inp = d.page.locator("#rubric_url")
if inp.count():
    inp.first.fill("https://github.com/example/v-day1")
    d.page.locator('form[action$="/copywork"] button[type=submit]').first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(1200)
    rec("day1 submit", flash=d.page.locator(".flash").inner_text().strip()[:200]
        if d.page.locator(".flash").count() else "(NO MESSAGE)", stamps=stamps())
    shot("62-v-day1-after-submit")
c = d.page.locator('form[action$="/complete"] button:visible')
if c.count():
    c.first.click(timeout=10000)
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(1500)
    b = d.text()
    rec("day1 complete", url=d.page.url.replace(BASE, ""),
        banner=[l.strip() for l in b.splitlines() if "POSTINGS" in l.upper() or "unlocked" in l.lower()][:4])
    shot("63-v-day1-complete-banner")

d.step("V3b", "Meter after Day 1 — does the core mechanic fire now?")
d.goto(f"{BASE}/sprints/{sid}")
b = d.text()
rec("meter after day1", lines=[l.strip() for l in b.splitlines()
                               if "unlocked" in l.lower() or "punched" in l.lower() or "%" in l][:8])
shot("64-v-meter-after-day1")

# ---------------------------------------------------------------- 4. Gate A reachability
d.step("V4", "Gate A — is project 1's rubric still empty (unwinnable)?")
for n in (2, 3, 4, 5):
    d.goto(f"{BASE}/sprints/{sid}/day/{n}")
    try:
        d.page.locator('button:text-is("Task")').first.click(timeout=5000)
        d.page.wait_for_timeout(500)
    except Exception:
        pass
    rec(f"day{n} rubric", checkboxes=d.page.locator('input[type=checkbox]').count(),
        copy=[l.strip() for l in d.text().splitlines() if "points are ticked" in l][:1],
        lesson_failed="generation failed" in d.text().lower())
    shot(f"65-v-day{n}-task")

# ---------------------------------------------------------------- 5. Phase B lock
d.step("V5", "Is Phase B still open on a Day-1 sprint?")
st = d.goto(f"{BASE}/sprints/{sid}/contract")
b = d.text()
rec("contract on day 1", status=st, locked="locked" in b.lower(),
    open_page="MOCK CONTRACT" in b.upper(), site_error="SITE ERROR" in b,
    requirements=[l.strip() for l in b.splitlines() if "Anonymized real job posting" in l][:1],
    brief=[l.strip() for l in b.splitlines() if "Client Brief" in l][:1])
shot("66-v-contract-day1")
st = d.goto(f"{BASE}/sprints/{sid}/proposals")
rec("proposals", status=st, locked="locked" in d.text().lower())

# ---------------------------------------------------------------- 6. mentor (fixed?)
d.step("V6", "Mentor — echo + thinking state + reply")
d.goto(f"{BASE}/mentor")
before = len(d.text())
try:
    d.page.locator("textarea, input[type=text]").first.fill("What should I build first?")
    d.page.locator('button:has-text("Send")').first.click(timeout=8000)
    d.page.wait_for_timeout(2500)
    mid = d.text()
    rec("mentor immediate", echoed="What should I build first?" in mid,
        thinking="thinking" in mid.lower(), delta=len(mid) - before)
    shot("67-v-mentor-thinking")
    got = False
    for _ in range(30):
        d.page.wait_for_timeout(2000)
        if len(d.text()) > len(mid) + 40:
            got = True
            break
    rec("mentor reply", got=got, secs_waited=60, chars=len(d.text()))
    shot("68-v-mentor-reply")
except Exception as e:
    rec("mentor error", err=str(e)[:200])

# ---------------------------------------------------------------- 7. profile / slug
d.step("V7", "Public profile — headline None? slug collision?")
st = d.goto(f"{BASE}/profile/me")
b = d.text()
rec("profile", status=st, url=d.page.url.replace(BASE, ""), none_literal=" None " in f" {b} ",
    lines=[l.strip() for l in b.splitlines() if l.strip()][:10])
shot("69-v-profile-me")

# ---------------------------------------------------------------- 8. zero-work complete
d.step("V8", "Zero-work 'Complete sprint' on this fresh Day-1 sprint")
btn = d.page.locator('button:has-text("Complete sprint"), a:has-text("Complete sprint")')
rec("button present on day 1", n=btn.count())
if btn.count():
    btn.first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(1500)
    b = d.text()
    rec("after zero-work complete", claims=[l.strip() for l in b.splitlines()
                                            if "complete" in l.lower() or "badge" in l.lower()][:6])
    shot("70-v-zero-work-complete")
    st = d.goto(f"{BASE}/sprints/{sid}/badge")
    rec("badge endpoint", status=st, text=d.text()[:200].replace("\n", " | "))
    shot("71-v-badge-endpoint")

(ART / "reverify.json").write_text(json.dumps(R, indent=1))
print("\nERRORS:", json.dumps(d.errors()[:15], indent=1))
d.close()
print("Re-verification done")
