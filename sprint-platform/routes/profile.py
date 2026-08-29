"""profile blueprint — public demand profile, badges, case-study portfolio (eng-spec §3 J7)."""
import datetime
from flask import Blueprint, render_template, redirect, url_for, g

from routes import require_login
from . import obtain_supabase
profile_bp = Blueprint("profile", __name__)


def _resolve_user(sb, slug):
    """Resolve a URL slug ('maya') to a user profile by display-name prefix.

    Deterministic: an exact full-name match wins over a first-name prefix
    match, and ties break on created_at so the same slug always resolves to
    the same profile even when multiple users share a first name.
    """
    rows = sb.table("user_profiles").select("*").execute().data
    rows.sort(key=lambda r: str(r.get("created_at") or ""))
    slug_l = slug.lower()
    prefix_match = None
    for r in rows:
        name = (r.get("display_name") or "").lower()
        if name == slug_l:
            return r
        if prefix_match is None and name.split()[0] == slug_l:
            prefix_match = r
    return prefix_match


def _days_ago(iso):
    if not iso:
        return 0
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
        return 0


def _badges(sb, user_id):
    from services.verification_service import passed
    rows = sb.table("badges").select("*").eq("user_id", user_id).execute().data
    out = []
    clusters = {r["cluster_key"]: r for r in
                sb.table("job_clusters").select("*").execute().data}
    sprints = {r["id"]: r for r in sb.table("sprints").select("*").execute().data}
    snapshots = {}
    # Latest reading per cluster (newest captured_at first → setdefault keeps it).
    for r in sb.table("demand_snapshots").select("cluster_key,job_count") \
            .order("captured_at", desc=True).execute().data:
        snapshots.setdefault(r["cluster_key"], r["job_count"])
    for b in rows:
        sprint_id = b.get("sprint_id")
        gate_b = passed(sb, sprint_id, "B")
        # Only show badges whose sprint passed gate B — badges are verification-backed.
        if not gate_b:
            continue
        key = b.get("cluster_key") or ""
        cluster = clusters.get(key) or {
            "cluster_key": key,
            "display_name": key.replace("-", " ").title() or "Sprint",
            "job_count": b.get("jobs_at_issue") or 0,
        }
        sprint = sprints.get(sprint_id) or {
            "proposals_sent": 0, "interviews_held": 0,
        }
        out.append({
            "cluster": cluster,
            "sprint": sprint,
            "jobs_at_issue": b.get("jobs_at_issue") or 0,
            # Trend source: the latest demand_snapshots reading for the cluster
            # (eng-spec §4.5 'powers "↑ from 410"'), falling back to the
            # jobs_at_issue stamped on the badge.
            "trend_from": snapshots.get(key, b.get("jobs_at_issue") or 0),
            "days_ago": _days_ago(b.get("issued_at")),
        })
    return out


def _case_studies(sb, user_id):
    rows = sb.table("case_studies").select("*").eq("user_id", user_id).execute().data
    return sorted(rows, key=lambda r: (bool(r.get("is_draft")), r.get("created_at") or ""))


@profile_bp.route("/profile/<slug>")
def public(slug):
    sb = obtain_supabase()
    profile = _resolve_user(sb, slug)
    if not profile:
        return render_template("profile.html", profile={"display_name": "Not found", "headline": ""},
                               badges=[], case_studies=[])
    return render_template(
        "profile.html",
        profile=profile,
        badges=_badges(sb, profile["user_id"]),
        case_studies=_case_studies(sb, profile["user_id"]),
    )


@profile_bp.route("/profile/me")
def me():
    gate = require_login()
    if gate:
        return gate
    sb = obtain_supabase()
    rows = sb.table("user_profiles").select("*").eq("user_id", g.user["id"]).limit(1).execute().data
    if rows:
        slug = (rows[0].get("display_name") or "me").split()[0].lower()
        return redirect(url_for("profile.public", slug=slug))
    return redirect(url_for("main.sprints"))
