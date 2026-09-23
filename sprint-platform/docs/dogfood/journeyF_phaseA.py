"""Journey F — finish Day 1 for real, then push through Phase A and probe Gate A.

Mutates only the dogfood account's own sprint.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "journeyF")
from harness import Dogfood, BASE, ART

sid = open(ART / "sprint_id.txt").read().strip()
d = Dogfood()
R = {"steps": []}


def rec(name, **kw):
    R["steps"].append(dict(name=name, **kw))
    print(f"  > {name}: " + json.dumps(kw, default=str)[:600], flush=True)


def task_tab():
    try:
        d.page.locator('button:text-is("Task")').first.click(timeout=6000)
        d.page.wait_for_timeout(600)
    except Exception as e:
        rec("task tab error", err=str(e)[:120])


def state_of_day(n):
    d.goto(f"{BASE}/sprints/{sid}/day/{n}")
    task_tab()
    body = d.text()
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    marks = {k: (k in body) for k in ["BUILD SUBMITTED", "MATCHES ALL POINTS", "VERIFIED",
                                      "Lesson generation failed", "Mark lesson watched"]}
    checks = d.page.locator('input[type=checkbox]').count()
    return marks, checks, lines, body


d.step("F1", "Did my Day-1 link actually register?")
marks, checks, lines, body = state_of_day(1)
rec("day1 state", marks=marks, checkboxes=checks)
print("  --- day1 task tab ---")
print(body[:2000])
d.shot("F1-day1-task-state")

d.step("F2", "Mark lesson watched (Day 1)")
btn = d.page.locator('button:has-text("Mark lesson watched")')
rec("lesson button", n=btn.count())
if btn.count():
    btn.first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=30000)
    d.page.wait_for_timeout(1200)
    rec("after watched", url=d.page.url.replace(BASE, ""),
        flash=d.page.locator(".flash").inner_text().strip()[:200] if d.page.locator(".flash").count() else "")
    d.shot("F2-after-lesson-watched")

d.step("F3", "Mark Day 1 complete")
d.goto(f"{BASE}/sprints/{sid}/day/1")
task_tab()
btn = d.page.locator('button:has-text("Mark day 1 complete"), a:has-text("Mark day 1 complete")')
rec("complete btn", n=btn.count())
if btn.count():
    btn.first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(2000)
    body = d.text()
    rec("after complete", url=d.page.url.replace(BASE, ""))
    d.shot("F3-after-day1-complete")
    print("  --- after completing day 1 ---")
    print(body[:2600])
    uptick = [l for l in body.splitlines() if "postings" in l.lower() or "complete" in l.lower()]
    rec("uptick lines", lines=uptick[:8])

d.step("F4", "Dashboard meter + phase state after Day 1")
d.goto(f"{BASE}/sprints/{sid}")
body = d.text()
rec("meter", lines=[l.strip() for l in body.splitlines()
                    if "unlock" in l.lower() or "of 5" in l or "/ 450" in l or "punched" in l][:10])
d.shot("F4-dashboard-after-day1")

d.step("F5", "Blitz Phase A: complete days 2-5 with a link each (Gate A integrity test)")
for n in range(2, 6):
    marks, checks, lines, body = state_of_day(n)
    rec(f"day{n} pre", marks=marks, checkboxes=checks,
        rubric_copy=[l for l in body.splitlines() if "points are ticked" in l][:1])
    # submit a link if the field exists
    inp = d.page.locator("#rubric_url")
    if inp.count():
        inp.fill(f"https://github.com/dana-dogfood/day{n}-build")
        d.page.locator('button:has-text("Send")').last.click()
        d.page.wait_for_load_state("domcontentloaded", timeout=30000)
        d.page.wait_for_timeout(1500)
        rec(f"day{n} submitted link", flash=d.page.locator(".flash").inner_text().strip()[:160]
            if d.page.locator(".flash").count() else "")
    # complete the day
    d.goto(f"{BASE}/sprints/{sid}/day/{n}")
    task_tab()
    btn = d.page.locator(f'button:has-text("Mark day {n} complete"), a:has-text("Mark day {n} complete")')
    if btn.count():
        btn.first.click()
        d.page.wait_for_load_state("domcontentloaded", timeout=30000)
        d.page.wait_for_timeout(1500)
        rec(f"day{n} completed", url=d.page.url.replace(BASE, ""))
    else:
        rec(f"day{n} no complete button", body=d.text()[:400])

d.step("F6", "Gate A verdict — is Phase B unlocked without any rubric criteria?")
d.goto(f"{BASE}/sprints/{sid}")
body = d.text()
d.shot("F6-dashboard-after-phaseA")
print("  --- dashboard ---")
print(body[:3200])
rec("phase B locked?", locked="Unlocks when Phase A passes verification" in body)
rec("meter final", lines=[l.strip() for l in body.splitlines()
                          if "unlock" in l.lower() or "punched" in l.lower()][:8])

(ART / "journeyF.json").write_text(json.dumps(R, indent=1))
print("\nERRORS:", json.dumps(d.errors()[:15], indent=1))
d.close()
print("Journey F done")
