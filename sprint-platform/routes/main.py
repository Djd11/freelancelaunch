"""main blueprint — landing, sprint picker, request-a-sprint, pricing (arch §4.2)."""
import datetime
import threading

from flask import Blueprint, render_template, request, redirect, url_for, g, current_app

from routes import require_login
from services.supabase_client import get_supabase
from services.sprint_planner import create_plan
from services.copywork_engine import create_projects
from services.lesson_engine import generate_sprint_content

main_bp = Blueprint("main", __name__)

# Empty-state shape for the landing counter card when no active clusters exist
# yet. Numbers are never fabricated — every counter shown on the landing page
# comes from job_clusters (eng-spec J1/J2 acceptance).
EMPTY_FEATURED = {
    "job_count": 0, "avg_rate": 0, "growth_score": 0, "display_name": "—",
}


def _active_clusters(sb):
    rows = sb.table("job_clusters").select("*").eq("status", "active").execute().data
    return sorted(rows, key=lambda r: (r.get("job_count") or 0), reverse=True)


def _open_cohort(sb, cluster_key):
    """Open a new active cohort for the cluster. Idempotent: if an active
    cohort already exists, return it instead of creating a duplicate."""
    existing = sb.table("cohorts").select("id") \
        .eq("cluster_key", cluster_key).eq("status", "active") \
        .limit(1).execute().data
    if existing:
        return existing[0]["id"]

    today = datetime.date.today()
    count = sb.table("cohorts").select("id").eq("cluster_key", cluster_key).execute().data
    row = sb.table("cohorts").insert({
        "cluster_key": cluster_key,
        "name": f"Cohort #{len(count) + 1}",
        "start_date": today.isoformat(),
        "end_date": (today + datetime.timedelta(days=13)).isoformat(),
        "status": "active",
    }).execute().data[0]
    return row["id"]


@main_bp.route("/")
def index():
    sb = get_supabase()
    clusters = _active_clusters(sb)
    featured = clusters[0] if clusters else EMPTY_FEATURED
    return render_template("landing.html", featured=featured, clusters=clusters)


@main_bp.route("/topics")
def topics():
    """Topics nav (eng-spec J1). The topic catalog IS the sprint catalog —
    route to the demand-validated sprint list (auth-gated)."""
    return redirect(url_for("main.sprints"))


@main_bp.route("/sprints")
def sprints():
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    clusters = _active_clusters(sb)
    return render_template("sprint_picker.html", clusters=clusters)


@main_bp.route("/sprints/request", methods=["POST"])
def request_sprint():
    gate = require_login()
    if gate:
        return gate
    skill = request.form.get("skill", "").strip().lower().replace(" ", "-")
    if skill:
        sb = get_supabase()
        existing = sb.table("job_clusters").select("*").eq("cluster_key", skill).limit(1).execute().data
        if not existing:
            sb.table("job_clusters").insert({
                "cluster_key": skill,
                "display_name": skill.replace("-", " ").title(),
                "icon": "🔎",
                "description": "Requested — we curate the live demand feed before we build it.",
                "job_count": 0,
                "avg_rate": 0,
                "growth_score": 0,
                "status": "requested",
            }).execute()
    return redirect(url_for("main.sprints"))


@main_bp.route("/sprints/<cluster_key>/start", methods=["POST"])
def start_sprint(cluster_key):
    """Enroll: create or resume a sprint for the cluster (idempotent).
    If user already has an active sprint for this cluster, redirect to it.
    Otherwise create a new sprint with plan + projects + background generation.
    """
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    cluster = sb.table("job_clusters").select("*").eq("cluster_key", cluster_key).limit(1).execute().data
    if not cluster:
        return redirect(url_for("main.sprints"))
    cluster = cluster[0]
    user_id = g.user["id"]

    # Idempotent: check for existing active sprint for this user + cluster
    existing = sb.table("sprints").select("id,current_day,status") \
        .eq("user_id", user_id).eq("cluster_key", cluster_key).eq("status", "active") \
        .order("started_at", desc=True).limit(1).execute().data
    if existing:
        existing_sprint_id = existing[0]["id"]
        return redirect(url_for("sprints.dashboard", sprint_id=existing_sprint_id))

    # Join the latest active cohort for this cluster, else open a new one.
    cohort = sb.table("cohorts").select("*").eq("cluster_key", cluster_key).eq("status", "active").limit(1).execute().data
    cohort_id = cohort[0]["id"] if cohort else _open_cohort(sb, cluster_key)

    sprint = sb.table("sprints").insert({
        "user_id": user_id,
        "cohort_id": cohort_id,
        "cluster_key": cluster_key,
        "phase": "A",
        "current_day": 1,
        "status": "active",
    }).execute().data[0]

    # Skeleton first (fast, always works), then LLM content fills in async —
    # the request never waits on the LLM (eng-spec §5: async generation, DB
    # progress log, frontend polling). Each sprint_days payload the worker
    # populates IS the progress the dashboard polls.
    create_plan(sb, sprint["id"])
    create_projects(sb, sprint["id"])
    sb.table("sprint_unlock_snapshots").upsert({
        "sprint_id": sprint["id"], "user_id": user_id,
        "completed_days": 0, "unlocked_count": 0, "total_in_cluster": 0, "last_delta": 0,
    }, on_conflict="sprint_id,user_id").execute()

    app = current_app._get_current_object()
    threading.Thread(
        target=_generate_in_background, args=(app, sprint["id"],), daemon=True,
    ).start()
    return redirect(url_for("sprints.dashboard", sprint_id=sprint["id"]))


def _generate_in_background(app, sprint_id):
    """Background LLM content generation — stamps visible errors on failure."""
    from services.lesson_engine import start_generation, stop_generation
    start_generation(sprint_id)
    try:
        with app.app_context():
            try:
                from supabase import create_client
                sb = create_client(
                    app.config.get("SUPABASE_URL") or "",
                    app.config.get("SUPABASE_SERVICE_KEY") or app.config.get("SUPABASE_KEY") or "",
                )
                generate_sprint_content(sb, sprint_id)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).exception("lesson generation failed for %s", sprint_id)
                # Stamp generation_error on the first empty day so the UI surfaces it
                try:
                    sb2 = create_client(
                        app.config.get("SUPABASE_URL") or "",
                        app.config.get("SUPABASE_SERVICE_KEY") or app.config.get("SUPABASE_KEY") or "",
                    )
                    days = sb2.table("sprint_days").select("day_no, action_payload") \
                        .eq("sprint_id", sprint_id).order("day_no").execute().data
                    for d in (days or []):
                        payload = d.get("action_payload") or {}
                        if not payload.get("lesson"):
                            payload["generation_error"] = f"Generation failed: {exc}"
                            sb2.table("sprint_days").update({"action_payload": payload}) \
                                .eq("sprint_id", sprint_id).eq("day_no", d["day_no"]).execute()
                            break
                except Exception:
                    logging.getLogger(__name__).exception("failed to stamp generation_error for %s", sprint_id)
    finally:
        stop_generation(sprint_id)


@main_bp.route("/pricing")
def pricing():
    return render_template("pricing.html")


@main_bp.route("/dashboard/")
def dashboard():
    """The sprint dashboard landing — redirects to the user's sprint picker."""
    gate = require_login()
    if gate:
        return gate
    return redirect(url_for("main.sprints"))
