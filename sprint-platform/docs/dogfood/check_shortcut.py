"""Decisive current-build check: can a Day-1 learner still self-declare the whole
sprint complete, and what does the product then claim?"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "shortcut2")
from harness import Dogfood, BASE, ART

sid = open(ART / "sprint_id_v.txt").read().strip()
d = Dogfood()
d.goto(f"{BASE}/sprints/{sid}")
b = d.text()
print("phase line:", [l.strip() for l in b.splitlines() if "SHIFT" in l][:2], flush=True)
print("generating?", "Generating your sprint content" in b, flush=True)
btn = d.page.locator('form[action$="/complete"] button')
print("complete-sprint form buttons found:", btn.count(), flush=True)
if btn.count():
    btn.first.click(timeout=15000)
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(2000)
    b = d.text()
    print("--- AFTER ZERO-WORK COMPLETE ---")
    print("\n".join([l for l in b.splitlines() if l.strip()][:26]))
    d.shot("77-zero-work-complete-current")
    st = d.goto(f"{BASE}/sprints/{sid}/badge")
    print("badge endpoint status:", st)
    print("badge page text:", d.text()[:300].replace("\n", " | "))
    d.shot("78-badge-endpoint-current")
else:
    print("No complete form on the dashboard right now.")
d.close()
