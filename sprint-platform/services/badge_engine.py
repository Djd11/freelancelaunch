"""
badge_engine — Demand-Validated badge issuance (engineering-spec §3 J7, §6).
A badge is issued ONLY when gate B passed AND the sprint completed — never
for "finishing a course". jobs_at_issue snapshots the live counter.
"""
from services.verification_service import passed


def issue(sb, sprint_id, user_id, cluster_key):
    """Issue a badge if gate B passed and the sprint is completed. Idempotent."""
    sprint_rows = sb.table("sprints").select("*").eq("id", sprint_id).limit(1).execute().data
    if not sprint_rows:
        return None
    sprint = sprint_rows[0]

    if not passed(sb, sprint_id, "B"):
        return None
    if sprint.get("status") != "completed":
        return None

    cluster_rows = sb.table("job_clusters").select("job_count").eq("cluster_key", cluster_key).limit(1).execute().data
    jobs_at_issue = cluster_rows[0].get("job_count", 0) if cluster_rows else 0

    # Idempotent: one badge per (user, cluster).
    existing = sb.table("badges").select("id").eq("user_id", user_id).eq("cluster_key", cluster_key).limit(1).execute().data
    if existing:
        return existing[0]

    res = sb.table("badges").insert({
        "user_id": user_id,
        "cluster_key": cluster_key,
        "sprint_id": sprint_id,
        "jobs_at_issue": jobs_at_issue,
    }).execute()
    badge = res.data[0] if res.data else None
    if badge:
        sb.table("sprints").update({"badge_id": badge["id"]}).eq("id", sprint_id).execute()
    return badge
