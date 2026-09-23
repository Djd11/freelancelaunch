"""Cleanly read the zero-work 'completed' sprint's dashboard, retrying past the
concurrency 500s, to confirm exactly what claim the product makes.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "rjread")
from harness import Dogfood, BASE, ART

sid = open(ART / "sprint_id_rj.txt").read().strip()
d = Dogfood()
d.goto(f"{BASE}/sprints/{sid}")
ok = False
for i in range(6):
    b = d.text()
    if "SITE ERROR" not in b and "Freelance" in b:
        ok = True
        break
    print(f"  retry {i+1}: got 500, waiting...", flush=True)
    time.sleep(4)
    d.goto(f"{BASE}/sprints/{sid}")
b = d.text()
print("RENDERED OK:", ok, "| SITE ERROR:", "SITE ERROR" in b, flush=True)
print("--- dashboard of a zero-work 'completed' sprint ---")
print("\n".join([l for l in b.splitlines() if l.strip()][:34]))
d.shot("84-rj-completed-dashboard")
(ART / "rj-completed-dashboard.txt").write_text(b)
d.close()
