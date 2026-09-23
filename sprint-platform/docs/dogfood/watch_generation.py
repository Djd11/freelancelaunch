"""Watch async content generation for the dogfood sprint."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "watch")
from harness import Dogfood, BASE, ART

sprint_id = open(ART / "sprint_id.txt").read().strip()
url = f"{BASE}/sprints/{sprint_id}/generation"
d = Dogfood()
d.goto(f"{BASE}/sprints/{sprint_id}")

start = time.time()
rows = []
while time.time() - start < float(os.environ.get("WATCH_SECS", "600")):
    try:
        r = d.page.request.get(url)
        body = r.text()
        code = r.status
    except Exception as e:
        body, code = f"ERR {e}", None
    el = round(time.time() - start)
    rows.append({"t": el, "status": code, "body": body[:300]})
    print(f"t+{el:>4}s  {body[:200]}", flush=True)
    if '"ready"' in body or '"done"' in body:
        break
    time.sleep(15)

d.goto(f"{BASE}/sprints/{sprint_id}")
txt = d.text()
d.shot("C0-dashboard-after-generation")
(ART / "watch.json").write_text(json.dumps(rows, indent=1))
(ART / "watch-dashboard.txt").write_text(f"URL: {d.page.url}\n{txt}\n")
print("\n--- dashboard text (first 1200) ---")
print(txt[:1200])
print("\nERRORS:", d.errors()[:10])
d.close()
