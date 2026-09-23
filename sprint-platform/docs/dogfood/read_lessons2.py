"""Dump the full rendered Day-3 page (lesson text + player markup) for quality review."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "quality2")
import harness
from harness import BASE, ART

B = json.load(open(ART / "journeyB.json"))
sid, email = B["sprint_id"], B["email"]
d = harness.Dogfood.__new__(harness.Dogfood)
d.t0 = time.time()
d.pw = harness.sync_playwright().start()
d.browser = d.pw.chromium.launch(headless=True)
d.ctx = d.browser.new_context(viewport={"width": 1440, "height": 900})
d.page = d.ctx.new_page()
d.events, d.timings = [], []
d._log_name = "quality2"
d.logf = open(ART / "quality2.jsonl", "a")
d._attach()

d.goto(f"{BASE}/auth/login")
d.page.fill("#email", email)
d.page.click('button[type=submit]')
d.page.wait_for_load_state("domcontentloaded", timeout=40000)

for n in (3, 11):
    d.goto(f"{BASE}/sprints/{sid}/day/{n}")
    txt = d.text()
    (ART / f"day{n}-full.txt").write_text(f"URL: {d.page.url}\n\n{txt}\n")
    d.shot(f"Q2-day{n}-lesson")
    print(f"===== DAY {n} ({len(txt)} chars) =====")
    print(txt[:3400])
    print("...")
    markup = d.page.evaluate("""() => {
      const a = document.querySelector('audio');
      const wrap = a ? a.closest('div,section') : null;
      return {audioSrc: a ? a.src.slice(0,160) : null,
              audioCount: document.querySelectorAll('audio').length,
              wrapClass: wrap ? wrap.className : null,
              wrapText: wrap ? wrap.innerText.slice(0,300) : null,
              buttons: [...document.querySelectorAll('button')].map(b=>b.innerText.trim()).filter(Boolean).slice(0,14)};""")
    print("PLAYER:", json.dumps(markup, indent=1))
    # task tab
    try:
        d.page.locator('button:text-is("Task")').first.click(timeout=5000)
        d.page.wait_for_timeout(600)
        t = d.text()
        (ART / f"day{n}-task.txt").write_text(t)
        print("TASK TAB:", [l.strip() for l in t.splitlines() if l.strip()][8:34])
        print("checkboxes:", d.page.locator('input[type=checkbox]').count())
        d.shot(f"Q2-day{n}-task")
    except Exception as e:
        print("task tab err", str(e)[:120])

d.ctx.close(); d.browser.close(); d.pw.stop()
