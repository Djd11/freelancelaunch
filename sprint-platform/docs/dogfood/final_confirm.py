"""Final confirmation pass: re-read the meter text, Gate B state, and Day 3/4/5
rubric availability, so every claim in the report has a fresh screenshot.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "final")
from harness import Dogfood, BASE, ART

B = json.load(open(ART / "journeyB.json"))
sid, email = B["sprint_id"], B["email"]
d = Dogfood()
R = {}

d.goto(f"{BASE}/auth/login")
d.page.fill("#email", email)
d.page.click('button[type=submit]')
d.page.wait_for_load_state("domcontentloaded", timeout=40000)

d.goto(f"{BASE}/sprints/{sid}")
body = d.text()
R["meter_lines"] = [l.strip() for l in body.splitlines()
                    if "unlock" in l.lower() or "punched" in l.lower() or "%" in l][:10]
print("METER:", json.dumps(R["meter_lines"], indent=1), flush=True)
d.shot("50-dashboard-meter-final")

for n in (3, 4, 5):
    d.goto(f"{BASE}/sprints/{sid}/day/{n}")
    try:
        d.page.locator('button:text-is("Task")').first.click(timeout=6000)
        d.page.wait_for_timeout(600)
    except Exception:
        pass
    R[f"day{n}"] = {"checkboxes": d.page.locator('input[type=checkbox]').count(),
                    "steps": d.page.locator("ol li").count(),
                    "copy": [l.strip() for l in d.text().splitlines() if "points are ticked" in l][:1]}
    print(f"DAY {n}: {R[f'day{n}']}", flush=True)
    d.shot(f"51-day{n}-rubric")

d.goto(f"{BASE}/sprints/{sid}/contract")
body = d.text()
R["contract"] = [l.strip() for l in body.splitlines() if "GATE" in l.upper() or "case study" in l.lower()][:8]
print("CONTRACT:", json.dumps(R["contract"], indent=1), flush=True)
d.shot("52-contract-gateB")

d.goto(f"{BASE}/sprints/{sid}/proposals")
R["proposals"] = d.text()[:400].replace("\n", " | ")
print("PROPOSALS:", R["proposals"][:260], flush=True)
d.shot("53-proposals-locked")

(ART / "final.json").write_text(json.dumps(R, indent=1))
d.close()
