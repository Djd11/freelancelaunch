"""
Demand Intelligence — Sprint Track

Source of truth for the live job feed and the Job Unlock Meter.

Responsibilities:
  1. Resolve a topic to a job cluster (get-or-create).
  2. Ingest curated postings into job_feed.
  3. Bucket postings into unlock_days 1..14 using the approved
     quick-win + escalating-value curve.
  4. Provide live counters (jobs open, avg rate).

The unlock curve: front-loaded for quick wins, back-loaded with premium value.
    v = 0.45*rate_pct + 0.35*(1 - experience_pct) + 0.20*review_pct
    unlock_day = min(14, 1 + floor(13 * v ** 1.8))
"""
import logging
from services.supabase_client import get_supabase

logger = logging.getLogger(__name__)

DAY_CAP = 14
CURVE_EXPONENT = 1.8
MAX_BUCKET_SIZE = 50


def _percentile(values, x):
    """Rank-based percentile of x within values (0..1)."""
    if not values:
        return 0.5
    below = sum(1 for v in values if v < x)
    return below / len(values)


def _experience_ordinal(exp):
    return {"entry": 0, "intermediate": 1, "expert": 2}.get((exp or "").lower(), 1)


def _value_score(row, rates, exps, reviews):
    """Composite value score in [0,1]. Higher = easier/better-to-land entry gig."""
    rate_pct = _percentile(rates, float(row.get("rate") or 0))
    exp_ordinal = _experience_ordinal(row.get("experience_needed"))
    exp_pct = _percentile(exps, exp_ordinal)
    review_pct = _percentile(reviews, float(row.get("review_count") or 0))
    return 0.45 * rate_pct + 0.35 * (1.0 - exp_pct) + 0.20 * review_pct


def _unlock_day(v):
    """Quick-win + escalating curve. Front-loads low-value gigs to early days."""
    return max(1, min(DAY_CAP, 1 + int(13 * (v ** CURVE_EXPONENT))))


def resolve_cluster(sb=None, slug=None, display_name=None):
    """Get-or-create a job_clusters row for a topic slug. Returns dict or None."""
    sb = sb or get_supabase()
    slug = slug or "email-automation"
    resp = sb.table("job_clusters").select("*").eq("cluster_key", slug).limit(1).execute()
    if resp.data:
        return resp.data[0]
    created = sb.table("job_clusters").insert({
        "cluster_key": slug,
        "display_name": display_name or slug.replace("-", " ").title(),
        "job_count": 0,
    }).execute()
    return created.data[0] if created.data else None


def live_counter(sb=None, cluster_key=None):
    """Return {'jobs': n, 'avg_rate': r} for a cluster, or zeros."""
    sb = sb or get_supabase()
    cluster_key = cluster_key or "email-automation"
    try:
        resp = sb.table("job_clusters").select("job_count,avg_rate").eq("cluster_key", cluster_key).limit(1).execute()
        if resp.data:
            row = resp.data[0]
            return {"jobs": row.get("job_count", 0), "avg_rate": row.get("avg_rate", 0)}
    except Exception as e:
        logger.warning(f"live_counter failed: {e}")
    return {"jobs": 0, "avg_rate": 0}


def ingest_feed(sb=None, cluster_key=None, postings=None):
    """Insert curated postings into job_feed, then bucket their unlock_days."""
    sb = sb or get_supabase()
    cluster = resolve_cluster(sb, cluster_key)
    if not cluster:
        return None

    for p in postings or []:
        try:
            sb.table("job_feed").insert({
                "cluster_key": cluster_key,
                "title": p.get("title", "Untitled posting"),
                "source": p.get("source", "curated"),
                "source_url": p.get("source_url", ""),
                "description": p.get("description", ""),
                "skills": p.get("skills", []),
                "rate": p.get("rate"),
                "experience_needed": p.get("experience_needed", "entry"),
                "review_count": p.get("review_count", 0),
                "unlock_day": DAY_CAP,  # placeholder; recomputed below
            }).execute()
        except Exception as e:
            logger.warning(f"ingest_feed insert failed: {e}")

    assign_unlock_days(sb, cluster_key)

    try:
        total = sb.table("job_feed").select("id", count="exact") \
            .eq("cluster_key", cluster_key).eq("status", "active").execute()
        count = getattr(total, "count", None) or len(total.data or [])
        avg = sb.table("job_feed").select("rate").eq("cluster_key", cluster_key).execute()
        rates = [r.get("rate") or 0 for r in (avg.data or [])]
        avg_rate = round(sum(rates) / len(rates), 2) if rates else 0
        sb.table("job_clusters").update({"job_count": count, "avg_rate": avg_rate}) \
            .eq("cluster_key", cluster_key).execute()
        sb.table("demand_snapshots").insert({
            "cluster_key": cluster_key, "job_count": count,
        }).execute()
    except Exception as e:
        logger.warning(f"counter refresh failed: {e}")

    return resolve_cluster(sb, cluster_key)


def assign_unlock_days(sb=None, cluster_key=None):
    """Recompute unlock_day for every active posting in a cluster."""
    sb = sb or get_supabase()
    resp = sb.table("job_feed").select("id,rate,experience_needed,review_count") \
        .eq("cluster_key", cluster_key).eq("status", "active").execute()
    rows = resp.data or []
    if not rows:
        return

    rates = [float(r.get("rate") or 0) for r in rows]
    exps = [_experience_ordinal(r.get("experience_needed")) for r in rows]
    reviews = [float(r.get("review_count") or 0) for r in rows]

    scored = [(_value_score(r, rates, exps, reviews), r["id"]) for r in rows]
    scored.sort()  # ascending by value → low value unlocks early

    assigned = {}
    for v, pid in scored:
        assigned[pid] = _unlock_day(v)

    # Guarantee lowest-value posting → Day 1 (quick win), highest → Day 14
    assigned[scored[0][1]] = 1
    assigned[scored[-1][1]] = DAY_CAP

    # Bucket-size cap (keep the feed browsable)
    buckets = {}
    for pid, day in assigned.items():
        buckets.setdefault(day, []).append(pid)
    for day, pids in buckets.items():
        if len(pids) > MAX_BUCKET_SIZE:
            for extra in pids[MAX_BUCKET_SIZE:]:
                assigned[extra] = min(DAY_CAP, day + 1)

    for pid, day in assigned.items():
        try:
            sb.table("job_feed").update({"unlock_day": day}).eq("id", pid).execute()
        except Exception as e:
            logger.warning(f"assign_unlock_days update failed: {e}")

    logger.info(f"Bucketed {len(rows)} postings in cluster '{cluster_key}' across days 1..14")
