"""Round 3 — GENERATION count (blocker #5), corrected column names.

The two fresh sprints were started by t2_generation.py; this counts how many of their
14 days have lesson content, and reports the elapsed time honestly.
"""
import sys, os, json, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flask import Flask  # noqa
import app as appmod
from harness import BASE, ART

started = json.load(open(ART / "t2gen_started.json"))
sa = appmod.app if hasattr(appmod, "app") else appmod.create_app()
out = {"elapsed_note": "sprints started by t2_generation.py; counted now"}
with sa.app_context():
    from services.supabase_client import get_supabase
    sb = get_supabase()
    for cluster, meta in started.items():
        sid = meta["sprint_id"]
        rows = sb.table("sprint_days").select("day_no,action_type,action_payload,is_done") \
            .eq("sprint_id", sid).order("day_no").execute().data
        have, err, pend = [], [], []
        for r in rows:
            pl = r.get("action_payload") or {}
            if (pl.get("lesson") or "").strip():
                have.append(r["day_no"])
            if pl.get("generation_error"):
                err.append(r["day_no"])
            if not (pl.get("lesson") or "").strip() and not pl.get("generation_error"):
                pend.append(r["day_no"])
        spr = sb.table("sprints").select("phase,current_day,status,created_at") \
            .eq("id", sid).execute().data
        created = spr[0]["created_at"] if spr else None
        out[cluster] = {
            "sprint_id": sid, "enroll_ms": meta["enroll_ms"], "created_at": created,
            "days_total": len(rows), "with_lesson": len(have), "error": len(err),
            "pending": len(pend), "pct_with_content": round(100 * len(have) / max(1, len(rows))),
            "error_days": err, "pending_days": pend,
            "lesson_chars": {r["day_no"]: len(((r.get("action_payload") or {}).get("lesson") or ""))
                             for r in rows},
            "rubrics_by_day": {r["day_no"]: (len((r.get("action_payload") or {}).get("rubric") or [])
                                             if isinstance((r.get("action_payload") or {}).get("rubric"), list)
                                             else None) for r in rows},
        }
        print(f"\n{cluster}  {sid}", flush=True)
        print(f"  created {created}", flush=True)
        print(f"  lesson present: {out[cluster]['with_lesson']}/{len(rows)} "
              f"({out[cluster]['pct_with_content']}%)  |  error: {len(err)}  |  pending: {len(pend)}", flush=True)
        print(f"  error days:   {err}", flush=True)
        print(f"  pending days: {pend}", flush=True)
        print(f"  enroll latency: {meta['enroll_ms']}ms", flush=True)
        print(f"  lesson chars: {out[cluster]['lesson_chars']}", flush=True)

# copy-work rubric availability is what decides Gate A reachability
print("\n=== copywork_projects rubric state for these sprints ===", flush=True)
with sa.app_context():
    from services.supabase_client import get_supabase
    sb = get_supabase()
    for cluster, meta in started.items():
        ps = sb.table("copywork_projects").select("*").eq("sprint_id", sid if False else meta["sprint_id"]) \
            .order("project_index").execute().data
        info = []
        for p in ps:
            r = p.get("rubric")
            info.append({"idx": p.get("project_index"),
                         "rubric": len(r) if isinstance(r, list) else r,
                         "steps": len(p.get("clone_steps") or []) if isinstance(p.get("clone_steps"), list) else None,
                         "done": p.get("done")})
        out[cluster]["projects"] = info
        print(f"  {cluster}: {info}", flush=True)

json.dump(out, open(ART / "t2gen_count.json", "w"), indent=1, default=str)
print("\ndone", flush=True)
