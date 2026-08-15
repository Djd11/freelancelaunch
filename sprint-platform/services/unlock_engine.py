"""
unlock_engine — Job Unlock Meter recompute (engineering-spec §4.1, arch §5.3).
On day completion: unlocked = COUNT(job_feed WHERE cluster_key=<sprint> AND
unlock_day <= completed_days); write a sprint_unlock_snapshots row; return
{newly, total, cluster}. The meter UI reads the snapshot O(1).
"""


def recompute(sb, sprint_id, user_id, cluster_key, completed_days):
    feed = sb.table("job_feed").select("unlock_day").eq("cluster_key", cluster_key).execute()
    total = len(feed.data)
    unlocked = sum(1 for r in feed.data if (r.get("unlock_day") or 99) <= completed_days)

    prev = sb.table("sprint_unlock_snapshots").select("*").eq("sprint_id", sprint_id).limit(1).execute().data
    old = prev[0].get("unlocked_count", 0) if prev else 0
    newly = max(0, unlocked - old)

    sb.table("sprint_unlock_snapshots").upsert({
        "sprint_id": sprint_id,
        "user_id": user_id,
        "completed_days": completed_days,
        "unlocked_count": unlocked,
        "total_in_cluster": total,
        "last_delta": newly,
    }, on_conflict="sprint_id,user_id").execute()

    return {
        "newly_unlocked": newly,
        "unlocked_count": unlocked,
        "total_in_cluster": total,
        "last_delta": newly,
    }
