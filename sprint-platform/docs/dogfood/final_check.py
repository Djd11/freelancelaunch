"""Final targeted checks on the current build:
 (a) does completing Day 1 now move the Job Unlock Meter?
 (b) is the zero-work 'Complete sprint' button still offered on Day 1?
 (c) is Gate A reachable when every copy-work project has an empty rubric?
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "finalcheck")
from harness import Dogfood, BASE, ART

sid = open(ART / "sprint_id_v.txt").read().strip()
email = [s for s in json.load(open(ART / "reverify.json"))["steps"]]
email = "reverify"  # display name used
# recover the email from the log
import re
m = re.search(r"reverify_\d+@example\.com", open(ART / "reverify.log").read())
email = m.group(0) if m else None
print("using account", email, "sprint", sid, flush=True)

d = Dogfood()
R = {}
# the saved session in artifacts/state.json already belongs to the reverify account
d.goto(f"{BASE}/sprints/{sid}")
print("  session ok ->", d.page.url.replace(BASE, ""), flush=True)


def stamps():
    return d.page.evaluate("""() => [...document.querySelectorAll('.stamp')].map(e =>
        ({label: e.innerText.trim(), lit: e.classList.contains('ok')}))""")


d.step("W1", "Dashboard on Day 1 — is 'Complete sprint' offered?")
d.goto(f"{BASE}/sprints/{sid}")
b = d.text()
R["complete_btn_on_day1"] = d.page.locator('button:has-text("Complete sprint"), a:has-text("Complete sprint")').count()
R["meter_before"] = [l.strip() for l in b.splitlines() if "unlocked" in l.lower()][:4]
print("  complete btn:", R["complete_btn_on_day1"], "| meter:", R["meter_before"], flush=True)
d.shot("72-w-dashboard-day1")

d.step("W2", "Complete Day 1 for real (watched + complete) and read the meter")
d.goto(f"{BASE}/sprints/{sid}/day/1")
w = d.page.locator('button.check-item:visible')
if w.count():
    w.first.click(timeout=10000)
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(1200)
d.goto(f"{BASE}/sprints/{sid}/day/1")
try:
    d.page.locator('button:text-is("Task")').first.click(timeout=5000)
    d.page.wait_for_timeout(500)
except Exception:
    pass
c = d.page.locator('form[action$="/complete"] button:visible')
R["complete_day1_btn"] = c.count()
print("  day1 complete btn:", c.count(), flush=True)
if c.count():
    c.first.click(timeout=10000)
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(2000)
    b = d.text()
    R["banner"] = [l.strip() for l in b.splitlines() if "POSTINGS" in l.upper() or "unlocked" in l.lower()][:5]
    print("  banner:", R["banner"], flush=True)
    d.shot("73-w-day1-banner")

d.step("W3", "Meter after Day 1")
d.goto(f"{BASE}/sprints/{sid}")
b = d.text()
R["meter_after"] = [l.strip() for l in b.splitlines() if "unlocked" in l.lower() or "punched" in l.lower()][:8]
print("  " + json.dumps(R["meter_after"], indent=1).replace("\n", "\n  "), flush=True)
d.shot("74-w-meter-after-day1")

d.step("W4", "Gate A reachability: tick every rubric that exists on days 2-5")
for n in (2, 3, 4, 5):
    d.goto(f"{BASE}/sprints/{sid}/day/{n}")
    try:
        d.page.locator('button:text-is("Task")').first.click(timeout=5000)
        d.page.wait_for_timeout(500)
    except Exception:
        pass
    boxes = d.page.locator('input[type=checkbox]')
    cnt = boxes.count()
    for i in range(cnt):
        try:
            boxes.nth(i).check(timeout=3000)
        except Exception:
            pass
    d.page.wait_for_timeout(800)
    inp = d.page.locator("#rubric_url")
    flash = ""
    if inp.count():
        inp.first.fill(f"https://github.com/example/v-day{n}")
        d.page.locator('form[action$="/copywork"] button[type=submit]').first.click()
        d.page.wait_for_load_state("domcontentloaded", timeout=40000)
        d.page.wait_for_timeout(1000)
        flash = d.page.locator(".flash").inner_text().strip()[:160] if d.page.locator(".flash").count() else "(none)"
    R[f"day{n}"] = {"checkboxes": cnt, "flash": flash, "stamps": stamps()}
    print(f"  day{n}: boxes={cnt} flash={flash!r}", flush=True)
    d.shot(f"75-w-day{n}-gateA")

d.step("W5", "Gate A verdict on the dashboard")
d.goto(f"{BASE}/sprints/{sid}")
b = d.text()
R["phase"] = [l.strip() for l in b.splitlines() if "SHIFT" in l][:3]
R["shiftA_state"] = [l.strip() for l in b.splitlines() if "punched" in l.lower()][:4]
R["shiftB_locked"] = "Unlocks when Phase A passes verification" in b
print("  ", json.dumps(R["phase"]), "locked:", R["shiftB_locked"], flush=True)
d.shot("76-w-gateA-verdict")

(ART / "finalcheck.json").write_text(json.dumps(R, indent=1))
d.close()
print("W done")
