"""Blueprint package. Shared query helpers for the sprint-platform routes."""
import uuid as _uuid

# Day → copy-work project index (1-based). Every Phase A copy-work day (2-5)
# must map so project 3 is reachable and Gate A can pass through the real day flow.
DAY_TO_PROJECT = {2: 1, 3: 1, 4: 2, 5: 3}

from flask import redirect, url_for, g

from services.supabase_client import get_supabase


def _is_uuid(value):
    """True when value is a syntactically valid UUID string.

    Postgres uuid columns reject anything else with 22P02, so malformed ids
    from URLs must short-circuit to None here — routes then return their
    specced not-found redirect instead of a 500.
    """
    if not isinstance(value, str):
        return False
    try:
        _uuid.UUID(value)
        return True
    except ValueError:
        return False


def require_login():
    """Redirect anonymous users to /auth/login (auth-gated surfaces)."""
    if not g.get("user"):
        return redirect(url_for("auth.login"))
    return None


def load_cluster(sb, cluster_key):
    rows = sb.table("job_clusters").select("*").eq("cluster_key", cluster_key).limit(1).execute().data
    return rows[0] if rows else None


def load_sprint(sb, sprint_id):
    if not _is_uuid(sprint_id):
        return None
    rows = sb.table("sprints").select("*").eq("id", sprint_id).limit(1).execute().data
    return rows[0] if rows else None


def load_cohort(sb, cohort_id):
    if not cohort_id or not _is_uuid(cohort_id):
        return None
    rows = sb.table("cohorts").select("*").eq("id", cohort_id).limit(1).execute().data
    return rows[0] if rows else None


def load_meter(sb, sprint_id):
    rows = sb.table("sprint_unlock_snapshots").select("*").eq("sprint_id", sprint_id).limit(1).execute().data
    return rows[0] if rows else {
        "completed_days": 0, "unlocked_count": 0, "total_in_cluster": 0, "last_delta": 0,
    }


def load_momentum(sb, user_id):
    rows = sb.table("user_momentum").select("*").eq("user_id", user_id).limit(1).execute().data
    if rows:
        return rows[0]
    return {"day_streak": 0, "best_streak": 0, "confidence": 50}


def load_day(sb, sprint_id, day_no):
    rows = sb.table("sprint_days").select("*").eq("sprint_id", sprint_id).eq("day_no", day_no).limit(1).execute().data
    return rows[0] if rows else None


def load_project(sb, sprint_id, index):
    if index is None:
        return None
    rows = sb.table("copywork_projects").select("*") \
        .eq("sprint_id", sprint_id).eq("project_index", index).limit(1).execute().data
    return rows[0] if rows else None


def load_brief(sb, sprint_id):
    rows = sb.table("capstone_briefs").select("*").eq("sprint_id", sprint_id).limit(1).execute().data
    return rows[0] if rows else None


def phase_a_done_days(sb, sprint_id):
    """Count completed Phase A days (days 1-5)."""
    rows = sb.table("sprint_days").select("day_no,is_done") \
        .eq("sprint_id", sprint_id).eq("phase", "A").execute().data
    return sum(1 for r in rows if r.get("is_done"))
