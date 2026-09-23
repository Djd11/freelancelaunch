"""Round 3 — generation count, robust to the dict-shaped lesson payload."""
import sys, os, json, datetime
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod
from harness import ART
sa = appmod.app if hasattr(appmod, "app") else appmod.create_app()
started = json.load(open(ART / "t2gen_started.json"))
out = {}
def size(l):
    return len(json.dumps(l)) if isinstance(l, (dict, list)) else len(str(l or ""))
with sa.app_context():
    from services.supabase_client import get_supabase
    sb = get_supabase()
    for cluster, meta in started.items():
        sid = meta["sprint_id"]
        rows = sb.table("sprint_days").select("day_no,action_payload").eq("sprint_id", sid).order("day_no").execute().data
        spr = sb.table("sprints").select("started_at,phase,current_day,status").eq("id", sid).execute().data
        created = spr[0]["started_at"] if spr else None
        have=[r["day_no"] for r in rows if (r.get("action_payload") or {}).get("lesson")]
        err=[r["day_no"] for r in rows if (r.get("action_payload") or {}).get("generation_error")]
        pend=[r["day_no"] for r in rows if not (r.get("action_payload") or {}).get("lesson")
              and not (r.get("action_payload") or {}).get("generation_error")]
        ps = sb.table("copywork_projects").select("project_index,rubric,clone_steps,done").eq("sprint_id", sid).order("project_index").execute().data
        proj=[{"idx":p["project_index"],"rubric":len(p["rubric"]) if isinstance(p.get("rubric"),list) else p.get("rubric"),
               "steps":len(p["clone_steps"]) if isinstance(p.get("clone_steps"),list) else None,"done":p.get("done")} for p in ps]
        mins = None
        if created:
            c = datetime.datetime.fromisoformat(created.replace("Z","+00:00"))
            mins = round((datetime.datetime.now(c.tzinfo)-c).total_seconds()/60, 1)
        out[cluster]={"sprint_id":sid,"enroll_ms":meta["enroll_ms"],"created_at":created,
                      "elapsed_min":mins,"days":len(rows),"with_lesson":len(have),"error":len(err),
                      "pending":len(pend),"pct":round(100*len(have)/max(1,len(rows))),
                      "error_days":err,"pending_days":pend,
                      "lesson_sizes":{r["day_no"]:size((r.get("action_payload") or {}).get("lesson")) for r in rows},
                      "projects":proj, "sprint":spr[0] if spr else None}
        print(f"\n{cluster}  {sid}", flush=True)
        print(f"  created {created}  elapsed {mins} min", flush=True)
        print(f"  lesson: {out[cluster]['with_lesson']}/{len(rows)} ({out[cluster]['pct']}%) | error {len(err)} | pending {len(pend)}", flush=True)
        print(f"  error days {err}\n  pending days {pend}", flush=True)
        print(f"  enroll {meta['enroll_ms']}ms | projects {proj}", flush=True)
json.dump(out, open(ART/"t2gen_count.json","w"), indent=1, default=str)
print("\nDONE", flush=True)
