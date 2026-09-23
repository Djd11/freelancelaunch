"""Read-only state audit behind the UI.

Cross-checks the numbers the marketing surfaces promise against what the database
actually holds, and records the dogfood sprint's gate/meter state. SELECTs only —
writes nothing.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
from flask import Flask
from config import Config
from services.supabase_client import get_supabase

app = Flask("audit", template_folder=os.path.join(ROOT, "templates"))
app.config.from_object(Config)
sid = open(os.path.join(HERE, "artifacts", "sprint_id.txt")).read().strip()

out = {}
with app.app_context():
    sb = get_supabase()

    clusters = sb.table("job_clusters").select(
        "cluster_key,display_name,status,job_count,avg_rate,growth_score").eq("status", "active").execute().data
    feed_counts = {}
    for c in clusters:
        k = c["cluster_key"]
        total = sb.table("job_feed").select("id").eq("cluster_key", k).execute().data or []
        active = sb.table("job_feed").select("id,source,unlock_day").eq("cluster_key", k).eq("status", "active").execute().data or []
        feed_counts[k] = {"cluster_job_count_claimed": c["job_count"],
                          "job_feed_rows": len(total),
                          "job_feed_active_rows": len(active),
                          "sources": sorted({(r.get("source") or "?") for r in active}),
                          "unlock_days": sorted({r.get("unlock_day") for r in active if r.get("unlock_day") is not None})}
    out["clusters_vs_feed"] = feed_counts

    out["cohorts"] = sb.table("cohorts").select("id,cluster_key,name,start_date,end_date,status") \
        .eq("status", "active").execute().data

    sprint = sb.table("sprints").select("*").eq("id", sid).limit(1).execute().data
    out["sprint"] = sprint[0] if sprint else None
    out["gates"] = sb.table("verification_reviews").select("*") \
        .eq("sprint_id", sid).execute().data
    out["projects"] = sb.table("copywork_projects").select(
        "project_index,title,done,submitted_url,rubric,clone_steps,gap_fill_topic").eq("sprint_id", sid).order("project_index").execute().data
    for p in out["projects"]:
        r = p.get("rubric")
        p["rubric_points"] = (len(r) if isinstance(r, list) else ("none" if r is None else "unparsed"))
        p["clone_steps_n"] = (len(p.get("clone_steps") or []) if isinstance(p.get("clone_steps"), list)
                              else "unparsed")
        p.pop("rubric", None)
        p.pop("clone_steps", None)
    days = sb.table("sprint_days").select("day_no,action_type,completed_at,action_payload").eq("sprint_id", sid) \
        .order("day_no").execute().data
    out["days"] = [{"day": x["day_no"], "action": x.get("action_type"), "completed": bool(x.get("completed_at")),
                    "has_lesson": bool((x.get("action_payload") or {}).get("lesson")),
                    "gen_error": (x.get("action_payload") or {}).get("generation_error")} for x in days]
    out["meter"] = sb.table("sprint_unlock_snapshots").select("*").eq("sprint_id", sid).execute().data
    out["proposals_n"] = len(sb.table("proposals").select("id").eq("sprint_id", sid).execute().data or [])

print(json.dumps(out, indent=1, default=str))
json.dump(out, open(os.path.join(HERE, "artifacts", "state_audit.json"), "w"), indent=1, default=str)
