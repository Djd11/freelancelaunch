"""Journey E — do the actual Day 1 work, then probe the gates like a QA engineer.

Order matters: validation probes (non-mutating) first, then the real submission,
then the gate/day-complete mechanics.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "journeyE")
from harness import Dogfood, BASE, ART

sid = open(ART / "sprint_id.txt").read().strip()
d = Dogfood()
R = {"steps": []}


def rec(name, **kw):
    R["steps"].append(dict(name=name, **kw))
    print(f"  > {name}: " + json.dumps(kw, default=str)[:500], flush=True)


def csrf():
    return d.page.evaluate("() => {const i=document.querySelector('input[name=csrf_token]'); return i?i.value:null}")


# ------------------------------------------------------- dashboard baseline
d.step("E1", "Dashboard baseline before doing anything")
d.goto(f"{BASE}/sprints/{sid}")
txt = d.text()
meter = [l for l in txt.splitlines() if "jobs unlocked" in l or "/ 450" in l or "unlocked" in l.lower()]
rec("meter lines", meter=meter[:6])
d.shot("E1-dashboard-before")

# ------------------------------------------------------- validation probes
d.step("E2", "Copy-work link validation (must reject junk, accept a real URL)")
d.goto(f"{BASE}/sprints/{sid}/day/1")
d.page.locator('button:text-is("Task")').first.click()
d.page.wait_for_timeout(500)
rub = d.page.locator("#rubric_url")
rec("rubric field present", present=rub.count() > 0)

for junk in ["", "not-a-url", "javascript:alert(1)", "ftp://example.com/x"]:
    if junk:
        rub.fill(junk)
    else:
        rub.fill("")
    d.page.locator('button:has-text("Send")').last.click()
    d.page.wait_for_timeout(1200)
    after = d.page.url
    flash = d.page.locator(".flash").inner_text() if d.page.locator(".flash").count() else ""
    rec("junk submission", sent=junk or "(empty)", landed=after.replace(BASE, ""), flash=flash.strip()[:160])
    d.shot(f"E2-junk-{(junk or 'empty').replace(':','-').replace('/','-')[:18]}")
    d.goto(f"{BASE}/sprints/{sid}/day/1")
    d.page.locator('button:text-is("Task")').first.click(timeout=5000)
    d.page.wait_for_timeout(400)

# ------------------------------------------------------- rubric integrity
d.step("E3", "Rubric integrity — how many check-points does Day 1 actually have?")
boxes = d.page.locator('input[type=checkbox]')
rec("rubric checkboxes on day 1", n=boxes.count())
pts = d.page.locator(".rubric li, [data-point], .point")
rec("rubric list items", n=pts.count())
body = d.text()
rec("vacuous-completion copy", present="all 0 points" in body.lower().replace("  ", " "),
    snippet=[l for l in body.splitlines() if "points are ticked" in l][:2])
d.shot("E3-rubric-empty")

# ------------------------------------------------------- the real submission
d.step("E4", "Submit a real build link (what a learner would do)")
rub = d.page.locator("#rubric_url")
rub.fill("https://github.com/dana-dogfood/email-recovery-flow")
d.page.locator('button:has-text("Send")').last.click()
d.page.wait_for_load_state("domcontentloaded", timeout=30000)
d.page.wait_for_timeout(1500)
rec("after submit", url=d.page.url.replace(BASE, ""), flash=(d.page.locator(".flash").inner_text().strip()[:200]
                                                             if d.page.locator(".flash").count() else ""))
d.shot("E4-after-copywork-submit")
print("  --- page after submit ---")
print(d.text()[:2200])

# ------------------------------------------------------- mark day complete
d.step("E5", "Mark day 1 complete")
d.goto(f"{BASE}/sprints/{sid}/day/1")
btn = d.page.locator('button:has-text("Mark day 1 complete"), a:has-text("Mark day 1 complete")')
rec("complete button", n=btn.count(), disabled=(btn.first.is_disabled() if btn.count() else None))
if btn.count():
    btn.first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=30000)
    d.page.wait_for_timeout(1500)
    d.shot("E5-after-day-complete")
    print("  --- after completing day 1 ---")
    print(d.text()[:2500])
    rec("after complete", url=d.page.url.replace(BASE, ""))

# ------------------------------------------------------- meter after
d.step("E6", "Job Unlock Meter after completing Day 1")
d.goto(f"{BASE}/sprints/{sid}")
txt = d.text()
rec("meter after", lines=[l for l in txt.splitlines() if "unlock" in l.lower() or "jobs" in l.lower()][:10])
d.shot("E6-dashboard-after-day1")

(ART / "journeyE.json").write_text(json.dumps(R, indent=1))
print("\nERRORS:", json.dumps(d.errors()[:12], indent=1))
d.close()
