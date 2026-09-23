"""Day 1 interaction as a real learner: click the tabs, try every action.

Runs against the live sprint in docs/dogfood/artifacts/sprint_id.txt.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "day1")
from harness import Dogfood, BASE, ART

sid = open(ART / "sprint_id.txt").read().strip()
d = Dogfood()
out = {"steps": []}


def rec(name, **kw):
    out["steps"].append(dict(name=name, **kw))
    print(f"  > {name}: " + json.dumps(kw)[:400], flush=True)


d.step("D1", "Day 1 page — tab structure")
d.goto(f"{BASE}/sprints/{sid}/day/1")
d.shot("D1-day1-lesson-tab")
tabs = d.page.eval_on_selector_all(
    "button, [role=tab], a",
    "els => els.map(e => (e.innerText||'').trim()).filter(t => t && t.length < 30)")
rec("visible controls", tabs=sorted(set(tabs))[:40])

d.step("D2", "Click the 'Task' tab")
clicked = False
for sel in ['button:text-is("Task")', 'text="Task"', '[data-tab="task"]']:
    try:
        loc = d.page.locator(sel)
        if loc.count():
            loc.first.click(timeout=5000)
            clicked = True
            break
    except Exception as e:
        rec("tab click error", sel=sel, err=str(e)[:150])
d.page.wait_for_timeout(700)
d.shot("D2-day1-task-tab")
rec("task tab clicked", ok=clicked)
print("  --- page after clicking Task ---")
print(d.text()[:2500])

d.step("D3", "Forms available on Day 1")
rec("forms", forms=d.forms())
print(json.dumps(d.forms(), indent=1)[:2000])

d.step("D4", "Try 'Mark lesson watched'")
try:
    loc = d.page.locator('button:has-text("Mark lesson watched"), a:has-text("Mark lesson watched")')
    rec("mark watched button count", n=loc.count())
    if loc.count():
        t = time.time()
        loc.first.click(timeout=8000)
        d.page.wait_for_load_state("networkidle", timeout=15000)
        rec("mark watched clicked", ms=round((time.time() - t) * 1000), url=d.page.url)
        d.shot("D3-after-mark-watched")
        print("  --- after mark watched ---")
        print(d.text()[:1800])
except Exception as e:
    rec("mark watched error", err=str(e)[:300])

(ART / "day1.json").write_text(json.dumps(out, indent=1))
print("\nERRORS:", d.errors()[:10])
d.close()
