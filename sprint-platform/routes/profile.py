"""profile blueprint — public demand profile, badges, case-study portfolio (eng-spec §3 J7)."""
import datetime
from flask import Blueprint, render_template, redirect, url_for, g

from routes import require_login
from . import obtain_supabase
profile_bp = Blueprint("profile", __name__)


def _first_name(profile):
    return ((profile.get("display_name") or "").split()[0] or "me").lower()


def _resolve_user(sb, slug):
    """Resolve a URL slug to a user profile.

    Two slug forms are supported:
      * unique form 'dana-1a2b3c' — first name + '-' + user_id prefix. Handed
        out to every user who is NOT the earliest account with that first name,
        so two people named Dana can never share one public URL.
      * legacy form 'dana' — exact full-name match wins over a first-name
        prefix match, and ties break on created_at (earliest account wins),
        keeping every pre-existing profile link stable.
    """
    rows = sb.table("user_profiles").select("*").execute().data
    rows.sort(key=lambda r: str(r.get("created_at") or ""))
    slug_l = slug.lower()
    # Unique suffixed form: base-<uidprefix>
    if "-" in slug_l:
        base, _, suffix = slug_l.rpartition("-")
        if len(suffix) >= 4 and all(c in "0123456789abcdef" for c in suffix):
            for r in rows:
                if _first_name(r) == base and str(r.get("user_id", "")).startswith(suffix):
                    return r
            return None
    prefix_match = None
    for r in rows:
        name = (r.get("display_name") or "").lower()
        if name == slug_l:
            return r
        if prefix_match is None and name.split()[0] == slug_l:
            prefix_match = r
    return prefix_match


def unique_slug(profile, all_profiles):
    """The public slug for one profile: bare first name for the earliest
    account with that first name, 'name-<uid6>' for everyone after it."""
    base = _first_name(profile)
    for r in sorted(all_profiles, key=lambda p: str(p.get("created_at") or "")):
        if _first_name(r) == base:
            return base if r["user_id"] == profile["user_id"] else f"{base}-{str(profile['user_id'])[:6]}"
    return base


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
                               badges=[], case_studies=[]), 404
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
        all_profiles = sb.table("user_profiles").select("user_id,display_name,created_at").execute().data
        return redirect(url_for("profile.public", slug=unique_slug(rows[0], all_profiles)))
    return redirect(url_for("main.sprints"))
