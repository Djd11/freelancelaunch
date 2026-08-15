"""clients blueprint — badge-filtered freelancer search (eng-spec §3 J7, arch §5.7)."""
import datetime
from flask import Blueprint, render_template, request

from services.supabase_client import get_supabase

clients_bp = Blueprint("clients", __name__)


def _days_ago(iso):
    if not iso:
        return 999
    try:
        if isinstance(iso, str):
            dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        else:
            dt = iso
        now = datetime.datetime.now(datetime.timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return max(0, (now - dt).days)
    except Exception:
        return 999


@clients_bp.route("/clients/freelancers")
def freelancers():
    sb = get_supabase()
    cluster_key = request.args.get("cluster", "")
    try:
        within_days = int(request.args.get("within_days", 30))
    except (TypeError, ValueError):
        within_days = 30

    badges = sb.table("badges").select("*").execute().data
    if cluster_key:
        badges = [b for b in badges if b.get("cluster_key") == cluster_key]
    badges = [b for b in badges if _days_ago(b.get("issued_at")) <= within_days]

    profiles = {r["user_id"]: r for r in sb.table("user_profiles").select("*").execute().data}
    sprints = {r["id"]: r for r in sb.table("sprints").select("*").execute().data}
    clusters = {r["cluster_key"]: r for r in sb.table("job_clusters").select("*").execute().data}

    out = []
    for b in badges:
        p = profiles.get(b.get("user_id"))
        if not p or p.get("is_public") is False:
            continue
        sprint = sprints.get(b.get("sprint_id"), {})
        cluster = clusters.get(b.get("cluster_key"), {})
        out.append({
            "display_name": p.get("display_name"),
            "headline": p.get("headline"),
            "jobs_now": cluster.get("job_count", 0),
            "days_ago": _days_ago(b.get("issued_at")),
            "proposals_sent": sprint.get("proposals_sent", 0),
            "interviews_held": sprint.get("interviews_held", 0),
            "contracts_won": sprint.get("contracts_won", 0),
        })

    all_clusters = sb.table("job_clusters").select("cluster_key,display_name").execute().data
    cluster_name = next((c["display_name"] for c in all_clusters if c["cluster_key"] == cluster_key), cluster_key or "any skill")

    return render_template(
        "clients.html", freelancers=out, all_clusters=all_clusters,
        cluster_key=cluster_key, cluster_name=cluster_name,
    )
