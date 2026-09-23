"""Phase D: Day-1 experience + gate faking.
Day 1: read lesson (full text captured), HEAD every media/asset URL,
mark watched w/o watching, mark day complete w/o any work.
Day 2 (first copywork day, project_index=1): submit empty, submit junk,
tick rubric via API + submit junk -> does the project count as done?
"""
import json, re, sys, time
from playwright.sync_api import sync_playwright

BASE = "https://freelancelaunch.onrender.com"
STATE = "docs/dogfood/live_qa/state_ravi.json"
SID = sys.argv[1]

out = {"console_errors": [], "bad_responses": [], "media": [], "gate_faking": {}}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900}, storage_state=STATE)
    page = ctx.new_page()
    page.on("console", lambda m: out["console_errors"].append({"url": page.url, "text": m.text}) if m.type == "error" else None)
    page.on("response", lambda r: out["bad_responses"].append({"url": r.url, "status": r.status, "page": page.url}) if r.status >= 400 else None)

    # ---- DAY 1 ----
    page.goto(BASE + f"/sprints/{SID}/day/1", wait_until="domcontentloaded", timeout=90000)
    out["day1_url"] = page.url
    out["day1_text"] = page.inner_text("body")
    out["day1_lesson_len"] = len(out["day1_text"])
    urls = page.evaluate("""() => {
      const u = new Set();
      document.querySelectorAll('img,video,audio,source,iframe').forEach(e => {
        if (e.src) u.add(e.src); if (e.poster) u.add(e.poster);
      });
      document.querySelectorAll('link[href], script[src]').forEach(e => u.add(e.href || e.src));
      document.querySelectorAll('a[href]').forEach(e => { if (/^https?:/.test(e.href)) u.add(e.href); });
      return [...u];
    }""")
    for u in urls:
        try:
            r = ctx.request.head(u, timeout=60000)
            out["media"].append({"url": u, "status": r.status})
        except Exception as e:
            out["media"].append({"url": u, "status": f"ERR {type(e).__name__}"})
        time.sleep(0.4)
    csrf = page.input_value("input[name=csrf_token]")

    # 1) mark watched without watching
    r = ctx.request.post(f"{BASE}/sprints/{SID}/day/1/watched", form={"csrf_token": csrf}, timeout=90000)
    out["gate_faking"]["d1_mark_watched"] = {"http": r.status, "url": r.url}

    # 2) mark day 1 complete with zero work
    r = ctx.request.post(f"{BASE}/sprints/{SID}/day/1/complete", form={"csrf_token": csrf}, timeout=90000)
    out["gate_faking"]["d1_complete_no_work"] = {"http": r.status, "final_url": r.url}

    # ---- DAY 2 (copywork, project_index=1) ----
    page.goto(BASE + f"/sprints/{SID}/day/2", wait_until="domcontentloaded", timeout=90000)
    out["day2_text_head"] = page.inner_text("body")[:2500]
    csrf2 = page.input_value("input[name=csrf_token]")

    # 3) submit copywork EMPTY (direct POST bypassing browser required)
    r = ctx.request.post(f"{BASE}/sprints/{SID}/day/2/copywork", form={"csrf_token": csrf2, "rubric_url": ""}, timeout=90000)
    body = re.sub(r"<[^>]+>", " ", r.text())
    out["gate_faking"]["copywork_empty"] = {"http": r.status, "flash": re.findall(r"(Paste a link[^.<]*|doesn't look like[^.<]*)", body)[:2]}

    # 4) submit junk URL with rubric UNTICKED
    r = ctx.request.post(f"{BASE}/sprints/{SID}/day/2/copywork", form={"csrf_token": csrf2, "rubric_url": "https://junk.example.com/x"}, timeout=90000)
    body = re.sub(r"<[^>]+>", " ", r.text())
    out["gate_faking"]["copywork_junk_unticked"] = {"http": r.status, "flash": re.findall(r"(Tick off all three[^.<]*|checklist hasn't[^.<]*)", body)[:2]}

    # 5) tick all rubric via API, then submit junk URL
    ticks = []
    for i in range(3):
        r = ctx.request.post(f"{BASE}/sprints/{SID}/day/2/rubric-check",
                             form={"csrf_token": csrf2, "project_index": "1", "rubric_index": str(i), "checked": "true"}, timeout=90000)
        ticks.append({"http": r.status, "body": r.text()[:80]})
    out["gate_faking"]["rubric_ticks"] = ticks
    r = ctx.request.post(f"{BASE}/sprints/{SID}/day/2/copywork", form={"csrf_token": csrf2, "rubric_url": "https://junk.example.com/x"}, timeout=90000)
    out["gate_faking"]["copywork_junk_after_ticks"] = {"http": r.status, "final_url": r.url}
    page.goto(BASE + f"/sprints/{SID}/day/2", wait_until="domcontentloaded", timeout=90000)
    txt = page.inner_text("body")
    out["gate_faking"]["d2_stamps"] = {
        "build_submitted_ok": bool(re.search(r"Build submitted", txt)),
        "matches_all_points": bool(re.search(r"Matches all points", txt)),
        "verified": bool(re.search(r"Verified", txt)),
    }
    # does the day-2 page now show project as done? (stamp ok class)
    out["gate_faking"]["d2_done_stamp_ok"] = "Day complete" in txt
    ctx.storage_state(path=STATE)
    browser.close()
print(json.dumps(out, indent=1))
