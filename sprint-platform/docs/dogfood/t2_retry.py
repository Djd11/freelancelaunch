"""Round 3 — does the new "Retry generation" button actually rescue a stuck day?

If it does, Gate A is reachable with user effort (honest empty state + working retry).
If it doesn't, the empty state is kind but the loop is still uncompletable.
Then: attempt the full honest loop Gate A -> Gate B -> proposals.
"""
import sys, os, json, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "t2retry")
from harness import Dogfood, BASE, ART

SID = "2e2566d8-ac2e-4a58-935d-e71c26a3c750"   # project 1 (days 2,3) still has rubric=0
d = Dogfood()
R = {"steps": []}


def rec(n, **kw):
    R["steps"].append(dict(name=n, **kw))
    print(f"  > {n}: " + json.dumps(kw, default=str)[:600], flush=True)


def shot(n):
    d.shot(n)
    print(f"    [shot] shots/{n}.png", flush=True)


def flash():
    f = d.page.locator(".flash")
    return f.inner_text().strip()[:300] if f.count() else "(NO MESSAGE)"


def boxes():
    return d.page.locator('input[type=checkbox]').count()


d.step("R1", "Click 'Retry generation' on a day whose checklist never arrived")
d.goto(f"{BASE}/sprints/{SID}/day/2")
try:
    d.page.locator('button:text-is("Task")').first.click(timeout=5000)
    d.page.wait_for_timeout(600)
except Exception:
    pass
rec("before retry", checkboxes=boxes(),
    empty_state=bool(re.search(r"hasn.t been written", d.text())))
retry = d.page.locator('button:has-text("Retry"), a:has-text("Retry")')
rec("retry control", count=retry.count(),
    label=retry.first.inner_text().strip()[:60] if retry.count() else None,
    href=retry.first.get_attribute("href") if retry.count() and retry.first.evaluate("e=>e.tagName") == "A" else None)
shot("d1-t2-retry-button")
if retry.count():
    t0 = time.time()
    retry.first.click(timeout=15000)
    d.page.wait_for_load_state("domcontentloaded", timeout=60000)
    rec("retry click", ms=round((time.time() - t0) * 1000), flash=flash(),
        url=d.page.url.replace(BASE, ""))
    shot("d2-t2-after-retry-click")

d.step("R2", "Poll day 2 for up to 5 minutes for the checklist to appear")
got = False
for i in range(25):
    time.sleep(12)
    d.goto(f"{BASE}/sprints/{SID}/day/2")
    try:
        d.page.locator('button:text-is("Task")').first.click(timeout=4000)
        d.page.wait_for_timeout(400)
    except Exception:
        pass
    if boxes() >= 3:
        got = True
        rec("checklist appeared", after_s=(i + 1) * 12, checkboxes=boxes())
        shot("d3-t2-rubric-appeared")
        break
if not got:
    rec("checklist still missing after 5 min", checkboxes=boxes(),
        copy=[l.strip() for l in d.text().splitlines() if re.search(r"checklist|Retry|generat", l, re.I)][:3])
    shot("d3-t2-rubric-still-missing")

(ART / "t2retry.json").write_text(json.dumps(R, indent=1))
print("\nERRORS:", json.dumps(d.errors()[:6], indent=1))
d.close()
print("RETRY test done")
