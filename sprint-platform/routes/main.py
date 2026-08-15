"""main blueprint — landing, sprint picker, request-a-sprint, pricing (arch §4.2)."""
from flask import Blueprint, render_template, request, redirect, url_for, g

from routes import require_login
from services.supabase_client import get_supabase

main_bp = Blueprint("main", __name__)

FALLBACK_FEATURED = {
    "job_count": 450, "avg_rate": 62, "growth_score": 18, "display_name": "Email Automation",
}


def _active_clusters(sb):
    rows = sb.table("job_clusters").select("*").eq("status", "active").execute().data
    return sorted(rows, key=lambda r: (r.get("job_count") or 0), reverse=True)


@main_bp.route("/")
def index():
    sb = get_supabase()
    clusters = _active_clusters(sb)
    featured = clusters[0] if clusters else FALLBACK_FEATURED
    return render_template("landing.html", featured=featured, clusters=clusters)


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


@main_bp.route("/sprints/<cluster_key>/start", methods=["GET", "POST"])
def start_sprint(cluster_key):
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    cluster = sb.table("job_clusters").select("*").eq("cluster_key", cluster_key).limit(1).execute().data
    if not cluster:
        return redirect(url_for("main.sprints"))
    cluster = cluster[0]
    user_id = g.user["id"]

    # Join the latest active cohort for this cluster, else start a new one.
    cohort = sb.table("cohorts").select("*").eq("cluster_key", cluster_key).eq("status", "active").limit(1).execute().data
    cohort_id = cohort[0]["id"] if cohort else None

    sprint = sb.table("sprints").insert({
        "user_id": user_id,
        "cohort_id": cohort_id,
        "cluster_key": cluster_key,
        "phase": "A",
        "current_day": 1,
        "status": "active",
    }).execute().data[0]

    phase_map = {d: "A" for d in range(1, 6)} | {d: "B" for d in range(6, 11)} | {d: "C" for d in range(11, 15)}
    for d in range(1, 15):
        phase = phase_map[d]
        action_type = "copywork" if d < 6 else ("contract" if d <= 8 else ("case-study" if d <= 10 else "proposal"))
        sb.table("sprint_days").insert({
            "sprint_id": sprint["id"], "phase": phase, "day_no": d,
            "title": f"Day {d}", "description": "",
            "action_type": action_type, "action_payload": {}, "is_done": False,
        }).execute()
    sb.table("sprint_unlock_snapshots").insert({
        "sprint_id": sprint["id"], "user_id": user_id,
        "completed_days": 0, "unlocked_count": 0, "total_in_cluster": 0, "last_delta": 0,
    }).execute()

    return redirect(url_for("sprints.dashboard", sprint_id=sprint["id"]))


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
