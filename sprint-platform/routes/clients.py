"""clients blueprint — badge-filtered freelancer search (eng-spec §3 J7, arch §5.7).

Powered by the public_freelancers view (db/schema.sql): badges joined with
user_profiles (is_public only), job_clusters, and sprints — fresh, verified
supply only. The view does the filtering; this route applies cluster + recency.
"""
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

    # public_freelancers already excludes non-public profiles (view WHERE clause).
    rows = sb.table("public_freelancers").select("*").execute().data
    if cluster_key:
        rows = [r for r in rows if r.get("cluster_key") == cluster_key]
    rows = [r for r in rows if _days_ago(r.get("issued_at")) <= within_days]

    freelancers = [{
        "display_name": r.get("display_name"),
        "headline": r.get("headline"),
        "jobs_now": r.get("jobs_now") or 0,
        "days_ago": _days_ago(r.get("issued_at")),
        "proposals_sent": r.get("proposals_sent") or 0,
        "interviews_held": r.get("interviews_held") or 0,
        "contracts_won": r.get("contracts_won") or 0,
    } for r in rows]

    all_clusters = sb.table("job_clusters").select("cluster_key,display_name").execute().data
    cluster_name = next((c["display_name"] for c in all_clusters if c["cluster_key"] == cluster_key), cluster_key or "any skill")

    return render_template(
        "clients.html", freelancers=freelancers, all_clusters=all_clusters,
        cluster_key=cluster_key, cluster_name=cluster_name,
    )
