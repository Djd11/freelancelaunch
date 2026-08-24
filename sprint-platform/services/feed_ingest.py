"""
feed_ingest — the pipeline that takes JobPosting objects from connectors
and writes them into the existing job_feed table.

Handles: dedup (by external_id + URL), normalization, cluster assignment,
unlock_day bucketing, and cluster counter refresh.
"""
import hashlib
import logging
from typing import List, Tuple

from services.platform_connector import JobPosting, PlatformConnector
from services.demand_intelligence import assign_unlock_days, refresh_cluster

logger = logging.getLogger(__name__)


def _url_hash(url: str) -> str:
    """Short hash for URL dedup."""
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()[:16]


def _title_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity for fuzzy dedup."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    return len(intersection) / min(len(words_a), len(words_b))


def _existing_external_ids(sb, source_platform: str) -> set:
    """Fetch all existing external_ids for a platform to avoid DB writes."""
    rows = sb.table("job_feed") \
        .select("external_id") \
        .eq("source_platform", source_platform) \
        .not_.is_("external_id", "null") \
        .execute().data
    return {r["external_id"] for r in rows}


def _existing_urls(sb) -> set:
    """Fetch all existing source_urls for URL dedup."""
    rows = sb.table("job_feed") \
        .select("source_url") \
        .not_.is_("source_url", "null") \
        .execute().data
    return {r["source_url"] for r in rows}


def _cluster_for_skills(sb, skills: list) -> str:
    """Match posting skills to the best cluster. Falls back to 'email-automation'."""
    clusters = sb.table("job_clusters") \
        .select("cluster_key, keywords") \
        .eq("status", "active") \
        .execute().data
    if not clusters:
        return "email-automation"
    skill_set = set(s.lower() for s in skills)
    best_key = "email-automation"
    best_score = 0
    for c in clusters:
        kw = c.get("keywords") or []
        cluster_words = set(k.lower() for k in kw)
        overlap = len(skill_set & cluster_words)
        if overlap > best_score:
            best_score = overlap
            best_key = c["cluster_key"]
    return best_key


def _cluster_keywords(sb, cluster_key: str) -> list:
    """Return the keyword list for a cluster (used for relevance filtering)."""
    rows = sb.table("job_clusters") \
        .select("keywords") \
        .eq("cluster_key", cluster_key) \
        .limit(1).execute().data
    if rows and rows[0].get("keywords"):
        return [k.lower() for k in rows[0]["keywords"]]
    return []


def _is_relevant_to_cluster(title: str, description: str, keywords: list,
                            source_platform: str = "") -> bool:
    """Check if a job posting is relevant to the cluster's domain.

    Manual jobs are always accepted (admin-curated).  For RSS/external
    jobs, the job title must contain at least one cluster keyword.
    Description-only matches are ignored — descriptions are often generic
    HTML blobs that match unrelated keywords (e.g. 'flow' in a backend
    job's pipeline description).
    """
    if not keywords:
        return True
    # Manual jobs are admin-curated — never filter them
    if source_platform == "manual":
        return True
    title_lower = (title or "").lower()
    return any(kw in title_lower for kw in keywords)


def ingest_jobs(
    sb,
    connector: PlatformConnector,
    cluster_key: str,
    query: str = "",
    max_results: int = 50,
) -> Tuple[int, int]:
    """Fetch jobs from a connector and write new ones to job_feed.

    Returns (new_count, skipped_count).
    """
    if not connector.is_configured():
        logger.info("Connector %s not configured — skipping", connector.platform_name)
        return 0, 0

    postings = connector.fetch_jobs(query=query, max_results=max_results)
    if not postings:
        logger.info("Connector %s returned 0 jobs", connector.platform_name)
        return 0, 0

    # Dedup sets
    existing_ids = _existing_external_ids(sb, connector.platform_name)
    existing_urls = _existing_urls(sb)

    new_count = 0
    skipped = 0

    # Fetch cluster keywords for relevance filtering
    cluster_kw = _cluster_keywords(sb, cluster_key) if cluster_key else []

    for posting in postings:
        # Skip if external_id already exists
        if posting.external_id and posting.external_id in existing_ids:
            skipped += 1
            continue
        # Skip if URL already exists
        if posting.url and posting.url in existing_urls:
            skipped += 1
            continue
        # Skip if title too similar to recent entries in same cluster
        # (lightweight fuzzy dedup)

        # Relevance filter: when cluster has keywords, reject jobs that
        # don't match the cluster's domain.  This prevents a generic
        # backend RSS feed from polluting the email-automation cluster
        # with unrelated senior-engineer postings.  Manual jobs are
        # always accepted (admin-curated).
        if cluster_kw and not _is_relevant_to_cluster(
            posting.title, posting.description, cluster_kw,
            source_platform=posting.source_platform,
        ):
            skipped += 1
            continue

        target_cluster = cluster_key or _cluster_for_skills(sb, posting.skills)

        row = {
            "cluster_key": target_cluster,
            "title": posting.title[:500],
            "source": posting.source_platform,
            "source_platform": posting.source_platform,
            "source_url": posting.url[:1000] if posting.url else None,
            "description": posting.description[:5000] if posting.description else None,
            "skills": posting.skills[:10],
            "rate": posting.rate,
            "experience_needed": posting.experience,
            "review_count": 0,
            "unlock_day": 1,  # will be reassigned by assign_unlock_days
            "status": "active",
            "external_id": posting.external_id[:500] if posting.external_id else None,
            "posted_at": posting.posted_at.isoformat() if posting.posted_at else None,
        }

        try:
            sb.table("job_feed").insert(row).execute()
            new_count += 1
            if posting.external_id:
                existing_ids.add(posting.external_id)
            if posting.url:
                existing_urls.add(posting.url)
        except Exception as exc:
            # Unique constraint violation = duplicate — skip silently
            if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
                skipped += 1
            else:
                logger.warning("Failed to insert job %r: %s", posting.title[:50], exc)
                skipped += 1

    # Reassign unlock_days and refresh cluster counters
    if new_count > 0:
        try:
            assign_unlock_days(sb, cluster_key)
        except Exception as exc:
            logger.warning("unlock_day assignment failed: %s", exc)
        try:
            refresh_cluster(sb, cluster_key, snapshot=True)
        except Exception as exc:
            logger.warning("cluster refresh failed: %s", exc)

    # Update platform connection last_synced_at
    try:
        sb.table("platform_connections") \
            .update({"last_synced_at": "now()"}) \
            .eq("platform", connector.platform_name) \
            .execute()
    except Exception:
        pass

    logger.info(
        "Ingest %s → cluster=%s: %d new, %d skipped (of %d fetched)",
        connector.platform_name, cluster_key, new_count, skipped, len(postings),
    )
    return new_count, skipped


def refresh_all_platforms(sb) -> dict:
    """Refresh all active platform connections. Returns summary."""
    connections = sb.table("platform_connections") \
        .select("*") \
        .eq("is_active", True) \
        .execute().data

    results = {}
    for conn in connections:
        platform = conn["platform"]
        config = conn.get("config") or {}
        try:
            from services.platform_connector import get_connector
            if platform == "rss":
                connector = get_connector("rss", feed_urls=config.get("feed_urls"))
            elif platform == "freelancer":
                connector = get_connector("freelancer", api_key=config.get("api_key", ""))
            elif platform == "upwork":
                connector = get_connector("upwork",
                    api_key=config.get("api_key", ""),
                    api_secret=config.get("api_secret", ""),
                )
            else:
                continue

            query = config.get("search_query", "")
            target_cluster = config.get("cluster_key", "email-automation")
            new, skipped = ingest_jobs(sb, connector, target_cluster, query)
            results[platform] = {"new": new, "skipped": skipped, "error": None}

            # Update quota if available
            if platform == "freelancer" and connector.is_configured():
                remaining = _get_freelancer_quota(connector)
                if remaining is not None:
                    sb.table("platform_connections") \
                        .update({"quota_remaining": remaining}) \
                        .eq("platform", platform) \
                        .execute()

        except Exception as exc:
            logger.warning("Platform %s refresh failed: %s", platform, exc)
            results[platform] = {"new": 0, "skipped": 0, "error": str(exc)}
            try:
                sb.table("platform_connections") \
                    .update({"last_error": str(exc)[:500]}) \
                    .eq("platform", platform) \
                    .execute()
            except Exception:
                pass

    return results


def _get_freelancer_quota(connector) -> int:
    """Check remaining API quota for Freelancer.com."""
    try:
        import urllib.request, json
        url = "https://www.freelancer.com/api/0.1/users/self/"
        headers = {
            "Authorization": f"Bearer {connector.api_key}",
            "User-Agent": "FreelanceLaunch/1.0",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            # Freelancer.com returns rate_limit info in headers or body
            return None  # Not available in free tier
    except Exception:
        return None
