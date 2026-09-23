"""Lesson-quality read on the sprint whose content DID partially generate.

Logs back in as the original dogfood account (email-only sign-in) and reads the
actual rendered lessons for the days that generated successfully, so the report
can judge real content quality rather than only the failures.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "quality")
from harness import Dogfood, BASE, ART

B = json.load(open(ART / "journeyB.json"))
sid, email = B["sprint_id"], B["email"]
d = Dogfood.__new__(Dogfood)          # start clean: ignore saved state
import harness
d.t0 = time.time()
d.pw = harness.sync_playwright().start()
d.browser = d.pw.chromium.launch(headless=True)
d.ctx = d.browser.new_context(viewport={"width": 1440, "height": 900})
d.page = d.ctx.new_page()
d.events, d.timings = [], []
d._log_name = "quality"
d.logf = open(ART / "quality.jsonl", "a")
d._attach()

d.goto(f"{BASE}/auth/login")
d.page.fill("#email", email)
d.page.click('button[type=submit]')
d.page.wait_for_load_state("domcontentloaded", timeout=40000)
print("logged in ->", d.page.url.replace(BASE, ""), flush=True)

report = {}
for n in [3, 4, 5, 8, 11]:
    d.goto(f"{BASE}/sprints/{sid}/day/{n}")
    body = d.text()
    lesson_el = d.page.evaluate("""() => {
      const sels = ['.lesson-body','.prose','.lesson','#lesson','.kinetic','.script'];
      for (const s of sels) { const e = document.querySelector(s); if (e && e.innerText.trim().length>50) return {sel:s, text:e.innerText}; }
      return null; }""")
    quiz = d.page.evaluate("""() => {
      const e = document.querySelector('.quiz, [data-quiz]');
      return e ? e.innerText.slice(0,800) : null; }""")
    player = d.page.evaluate("""() => ({
      canvas: document.querySelectorAll('canvas').length,
      video: document.querySelectorAll('video').length,
      audio: document.querySelectorAll('audio').length,
      playerDiv: !!document.querySelector('#player, .player, .two-panel, .twopanel') })""")
    report[f"day{n}"] = {
        "chars": len(body),
        "generating": "Generating your lesson" in body,
        "failed": "generation failed" in body.lower(),
        "lesson_extracted": (lesson_el or {}).get("text", "")[:2600],
        "quiz": quiz,
        "player": player,
        "has_key_points": "key point" in body.lower(),
        "has_pitfalls": "pitfall" in body.lower(),
    }
    d.shot(f"Q-day{n}")
    print(f"day{n}: chars={len(body)} gen={report[f'day{n}']['generating']} "
          f"fail={report[f'day{n}']['failed']} player={player}", flush=True)

(ART / "lesson_quality.json").write_text(json.dumps(report, indent=1))
for k, v in report.items():
    print("\n=====", k, "=====")
    print(v["lesson_extracted"][:1500])
    if v["quiz"]:
        print("--- quiz ---", v["quiz"][:400])
d.save_state()
d.ctx.close(); d.browser.close(); d.pw.stop()
