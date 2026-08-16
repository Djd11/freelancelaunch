"""
demand_intelligence — feed ingest helpers, unlock_day bucketing, live
counters, demand snapshots (architecture.md §4.3, eng-spec §4.5).

v1 scope: deterministic helpers callable on demand (an admin "refresh demand"
action, or the nightly cron looping over active clusters). Nothing here runs
automatically on a read — marketing counters are seeded and never clobbered
by an implicit recompute (eng-spec §4.5: "the UI reads job_clusters (O(1)),
never a live query").
"""

# Day-1-largest, Day-14-highest-value bucket distribution (eng-spec §4.1).
DAY_SIZE_PCT = [12, 11, 10, 9, 8, 8, 7, 6, 6, 5, 5, 4, 4, 5]

_EXPERIENCE_LEVELS = {"entry": 1, "intermediate": 2, "expert": 3}


def _composite_value(row):
    """Composite posting value v = clamp(0.45·rate_pct + 0.35·(1−experience_pct)
    + 0.20·review_pct), ranked descending easiest→hardest (eng-spec §4.1)."""
    rate = float(row.get("rate") or 0)
    exp = _EXPERIENCE_LEVELS.get((row.get("experience_needed") or "").lower(), 2)
    rate_pct = min(rate / 400.0, 1.0)
    experience_pct = (exp - 1) / 2.0
    review_pct = min(float(row.get("review_count") or 0) / 50.0, 1.0)
    return 0.45 * rate_pct + 0.35 * (1 - experience_pct) + 0.20 * review_pct


def assign_unlock_days(sb, cluster_key):
    """Assign unlock_day (1-14) to the cluster's postings by quantile bucket.
    Day 1 is the largest bucket (quick win); Day 14 holds the highest-value
    postings; every bucket has at least one posting (eng-spec §4.1)."""
    feed = sb.table("job_feed").select("*").eq("cluster_key", cluster_key).execute().data
    if not feed:
        return 0
    ranked = sorted(feed, key=_composite_value, reverse=True)
    n = len(ranked)
    buckets = [max(1, round(n * pct / 100.0)) for pct in DAY_SIZE_PCT]
    day = 0
    for idx, row in enumerate(ranked):
        while day < 13 and idx >= sum(buckets[: day + 1]):
            day += 1
        sb.table("job_feed").update({"unlock_day": day + 1}).eq("id", row["id"]).execute()
    return n


def refresh_cluster(sb, cluster_key, snapshot=True):
    """Recompute the cluster's live counters from its active feed postings and
    (optionally) write a demand_snapshots time-series row (powers '↑ from 410')."""
    feed = sb.table("job_feed").select("rate") \
        .eq("cluster_key", cluster_key).eq("status", "active").execute().data
    job_count = len(feed)
    rates = [float(r.get("rate") or 0) for r in feed if r.get("rate")]
    avg_rate = round(sum(rates) / len(rates)) if rates else 0
    # last_synced_at defaults to now() — the column is not touched here.
    sb.table("job_clusters").update({
        "job_count": job_count,
        "avg_rate": avg_rate,
    }).eq("cluster_key", cluster_key).execute()
    if snapshot:
        sb.table("demand_snapshots").insert({
            "cluster_key": cluster_key,
            "job_count": job_count,
            "avg_rate": avg_rate,
        }).execute()
    return {"cluster_key": cluster_key, "job_count": job_count, "avg_rate": avg_rate}
