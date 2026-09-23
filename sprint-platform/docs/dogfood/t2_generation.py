"""Round 3 — GENERATION re-test (blocker #5).

Starts two fresh sprints, waits 6 minutes (the captain's stated window), then counts
how many of the 14 days actually have lesson content. Round 2 baseline: ~50% of days
ended in `error` (7/14 on one sprint) with timeout=90. Timeouts are now 240s.
"""
import sys, os, json, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "t2gen")
from harness import Dogfood, BASE, ART

d = Dogfood()
d.goto(f"{BASE}/sprints")
if "Sign out" not in d.text():
    print("!! no session", flush=True)
    sys.exit(1)

started = {}
for cluster in ("web-scraping", "ai-chatbots"):
    d.goto(f"{BASE}/sprints")
    t = time.time()
    sel = f'form[action$="/{cluster}/start"] button'
    if d.page.locator(sel).count():
        d.page.locator(sel).first.click()
        d.page.wait_for_load_state("domcontentloaded", timeout=120000)
        sid = d.page.url.rstrip("/").split("/")[-1]
        started[cluster] = {"sprint_id": sid, "enroll_ms": round((time.time() - t) * 1000)}
        print(f"  started {cluster}: {sid} in {started[cluster]['enroll_ms']}ms", flush=True)
        d.shot(f"a1-t2-enrolled-{cluster}")
    else:
        print(f"  no start button for {cluster}", flush=True)

(ART / "t2gen_started.json").write_text(json.dumps(started, indent=1))

print("waiting 6 minutes for background generation...", flush=True)
time.sleep(360)

# read-only DB truth via the app's own client
from flask import Flask
import app as appmod
sa = appmod.app if hasattr(appmod, "app") else appmod.create_app()
with sa.app_context():
    from services.supabase_client import get_supabase
    sb = get_supabase()
    out = {}
    for cluster, meta in started.items():
        sid = meta["sprint_id"]
        rows = sb.table("sprint_days").select(
            "day,action,generation_status,lesson_content,generation_error"
        ).eq("sprint_id", sid).order("day").execute().data
        have = [r["day"] for r in rows if (r.get("lesson_content") or "").strip()]
        err = [r["day"] for r in rows if r.get("generation_status") == "error"]
        pend = [r["day"] for r in rows if r.get("generation_status") not in ("done", "error")]
        out[cluster] = {
            "sprint_id": sid, "enroll_ms": meta["enroll_ms"],
            "days_total": len(rows),
            "days_with_lesson": len(have),
            "days_error": len(err),
            "days_pending": len(pend),
            "pct_with_content": round(100 * len(have) / max(1, len(rows))),
            "error_days": err, "pending_days": pend,
            "lesson_chars": {r["day"]: len(r.get("lesson_content") or "") for r in rows},
        }
        print(f"\n{cluster} ({sid})", flush=True)
        print(f"  with lesson: {out[cluster]['days_with_lesson']}/{len(rows)} "
              f"({out[cluster]['pct_with_content']}%) | error: {len(err)} | pending: {len(pend)}", flush=True)
        print(f"  error days: {err}", flush=True)
        print(f"  enroll latency: {meta['enroll_ms']}ms", flush=True)

# also check the UI for the same sprints
for cluster, meta in started.items():
    d.goto(f"{BASE}/sprints/{meta['sprint_id']}")
    t = d.text()
    out[cluster]["ui_generating_banner"] = "Generating your sprint content" in t
    out[cluster]["ui_progress"] = [l.strip() for l in t.splitlines() if re.match(r"^\d+ / 14$", l.strip())] \
        if (re := __import__("re")) else []
    out[cluster]["meter"] = [l.strip() for l in t.splitlines() if "unlocked" in l.lower()][:3]
    out[cluster]["cohort"] = [l.strip() for l in t.splitlines() if "COHORT" in l][:1]
    d.shot(f"a2-t2-dashboard-{cluster}")

(ART / "t2gen.json").write_text(json.dumps(out, indent=1))
d.close()
print("\nGENERATION test done", flush=True)
