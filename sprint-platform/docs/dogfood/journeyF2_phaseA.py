"""Journey F2 — finish Day 1 properly (both tabs), then blitz Phase A and probe Gate A.

Tab handling matters: the Lesson panel and Task panel are separate; controls in
the hidden panel are not clickable until its tab is active.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "journeyF2")
from harness import Dogfood, BASE, ART

sid = open(ART / "sprint_id.txt").read().strip()
d = Dogfood()
R = {"steps": []}


def rec(name, **kw):
    R["steps"].append(dict(name=name, **kw))
    print(f"  > {name}: " + json.dumps(kw, default=str)[:600], flush=True)


def open_day(n, tab="Task"):
    d.goto(f"{BASE}/sprints/{sid}/day/{n}")
    try:
        d.page.locator(f'button:text-is("{tab}")').first.click(timeout=6000)
        d.page.wait_for_timeout(600)
    except Exception as e:
        rec("tab error", day=n, tab=tab, err=str(e)[:120])
    return d.text()


def visible_click(text, timeout=8000):
    loc = d.page.locator(f'button:visible:has-text("{text}"), a:visible:has-text("{text}")')
    if loc.count() == 0:
        return False
    loc.first.click(timeout=timeout)
    d.page.wait_for_load_state("domcontentloaded", timeout=30000)
    d.page.wait_for_timeout(1500)
    return True


d.step("F1", "Day 1 — Lesson tab: mark watched")
body = open_day(1, "Lesson")
rec("lesson tab", has_fail="generation failed" in body.lower())
ok = visible_click("Mark lesson watched")
rec("mark watched clicked", ok=ok, flash=d.page.locator(".flash").inner_text().strip()[:160]
    if d.page.locator(".flash").count() else "")
d.shot("F2-day1-after-watched")

d.step("F2", "Day 1 — Task tab: current state")
body = open_day(1, "Task")
rec("day1 task", submitted="BUILD SUBMITTED" in body, verified="VERIFIED" in body,
    checkboxes=d.page.locator('input[type=checkbox]').count())
d.shot("F2-day1-task")

d.step("F3", "Day 1 — Mark day complete")
ok = visible_click("Mark day 1 complete")
rec("complete clicked", ok=ok, url=d.page.url.replace(BASE, ""))
body = d.text()
print("  --- after Day 1 complete ---")
print(body[:2200])
rec("uptick", lines=[l.strip() for l in body.splitlines() if "postings" in l.lower()][:6])
d.shot("F3-after-day1-complete")

d.step("F4", "Dashboard after Day 1")
d.goto(f"{BASE}/sprints/{sid}")
body = d.text()
rec("meter", lines=[l.strip() for l in body.splitlines()
                    if "unlock" in l.lower() or "punched" in l.lower() or "of 5" in l][:8])
d.shot("F4-dashboard-after-day1")

d.step("F5", "Blitz days 2-5: submit a link, complete the day (Gate A integrity)")
for n in range(2, 6):
    body = open_day(n, "Task")
    cb = d.page.locator('input[type=checkbox]:visible').count()
    vacuous = [l.strip() for l in body.splitlines() if "points are ticked" in l]
    rec(f"day{n} task", checkboxes=cb, vacuous=vacuous[:1],
        lesson_fail="couldn't be written" in body,
        project=[l.strip() for l in body.splitlines() if "PROJECT" in l.upper()][:1])
    inp = d.page.locator("#rubric_url:visible")
    if inp.count():
        inp.first.fill(f"https://github.com/dana-dogfood/day{n}-build")
        visible_click("Send")
        rec(f"day{n} link sent", flash=d.page.locator(".flash").inner_text().strip()[:140]
            if d.page.locator(".flash").count() else "")
    # tick any visible rubric boxes
    body = open_day(n, "Task")
    boxes = d.page.locator('input[type=checkbox]:visible')
    for i in range(boxes.count()):
        try:
            boxes.nth(i).check()
        except Exception:
            pass
    if boxes.count():
        visible_click("Send") if d.page.locator("#rubric_url:visible").count() else None
    open_day(n, "Task")
    ok = visible_click(f"Mark day {n} complete")
    rec(f"day{n} completed", ok=ok, url=d.page.url.replace(BASE, ""))
    d.shot(f"F5-day{n}-after")

d.step("F6", "Gate A verdict")
d.goto(f"{BASE}/sprints/{sid}")
body = d.text()
print("  --- dashboard after Phase A blitz ---")
print(body[:3500])
rec("phaseB still locked", "Unlocks when Phase A passes verification" in body)
rec("meter", lines=[l.strip() for l in body.splitlines()
                    if "unlock" in l.lower() or "punched" in l.lower()][:8])
d.shot("F6-dashboard-after-phaseA")
(ART / "journeyF2.json").write_text(json.dumps(R, indent=1))
print("\nERRORS:", json.dumps(d.errors()[:15], indent=1))
d.close()
print("F2 done")
