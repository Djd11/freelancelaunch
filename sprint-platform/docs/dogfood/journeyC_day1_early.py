"""Open Day 1 immediately after enrollment (content may still be generating)."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "day1_early")
from harness import Dogfood, BASE, ART

sid = open(ART / "sprint_id.txt").read().strip()
d = Dogfood()
d.step("C0", "Dashboard -> Open Day 1 (while content is still generating)")
d.goto(f"{BASE}/sprints/{sid}")
btn = d.page.locator('a:has-text("Open Day 1"), a:has-text("Day 1")')
print("  day1 links found:", btn.count())
d.goto(f"{BASE}/sprints/{sid}/day/1")
d.shot("C1-day1-while-generating")
txt = d.text()
print("  --- Day 1 as a newcomer sees it (first 3500 chars) ---")
print(txt[:3500])
(ART / "C1-day1-early.txt").write_text(f"URL: {d.page.url}\n{txt}\n")
print("\n  ERRORS:", d.errors()[:10])
d.close()
