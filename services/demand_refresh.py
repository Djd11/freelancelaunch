"""
Nightly job to refresh topic_intelligence with live platform data
Run via cron: 0 3 * * * cd /path/to/web-app && python -m services.demand_refresh
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional
from services.supabase_client import get_supabase_service
from services.platform_scraper import scrape_all_platforms, PlatformDemandData

logger = logging.getLogger(__name__)

# Platform weights for aggregation (Upwork has highest signal for hourly freelance)
PLATFORM_WEIGHTS = {"upwork": 1.0, "fiverr": 0.8, "contra": 0.6}

# Minimum jobs to consider a platform signal valid
MIN_JOBS_FOR_SIGNAL = 5


@dataclass
class TopicIntelligence:
    """Aggregated intelligence for a topic"""
    topic: str
    freelance_job_count: int
    avg_rate: float
    demand_trend: str
    viability_score: int
    platform_breakdown: dict  # per-platform raw data
    last_updated: str


async def fetch_curated_topics(sb) -> list[dict]:
    """Fetch active curated topics from the database (not hardcoded)."""
    resp = sb.table("topics").select("slug, name, is_curated").eq("is_curated", True).eq("status", "active").execute()
    return resp.data or []


async def refresh_topic_intelligence(sb, topic: dict) -> Optional[TopicIntelligence]:
    """Refresh demand data for a single topic."""
    slug = topic["slug"]
    query = topic["name"]
    logger.info(f"Refreshing demand data for {query} (slug: {slug})...")

    try:
        # Scrape all platforms in parallel with timeout
        results = await asyncio.wait_for(scrape_all_platforms(query), timeout=120)

        platform_data = {}
        for platform in ["upwork", "fiverr", "contra"]:
            data = results.get(platform)
            if isinstance(data, Exception):
                logger.error(f"{platform} scrape failed for {slug}: {data}")
                platform_data[platform] = None
            elif data and data.job_count >= MIN_JOBS_FOR_SIGNAL:
                platform_data[platform] = data
            else:
                logger.debug(f"{platform}: insufficient data for {slug} (jobs: {data.job_count if data else 0})")
                platform_data[platform] = None

        # Aggregate data (weighted by platform importance)
        valid_platforms = [(p, d) for p, d in platform_data.items() if d is not None]

        if not valid_platforms:
            logger.warning(f"No valid platform data for {slug}, keeping existing intelligence")
            return None

        total_weighted_jobs = sum(
            d.job_count * PLATFORM_WEIGHTS.get(p, 0.5) for p, d in valid_platforms
        )
        total_jobs = sum(d.job_count for _, d in valid_platforms)

        weighted_rate = sum(
            d.avg_rate * d.job_count * PLATFORM_WEIGHTS.get(p, 0.5)
            for p, d in valid_platforms
        ) / total_weighted_jobs if total_weighted_jobs > 0 else 0

        # Determine overall trend (weighted by platform importance)
        trend_scores = {"growing": 2, "stable": 1, "declining": 0}
        weighted_trend_score = sum(
            trend_scores.get(d.trend, 1) * PLATFORM_WEIGHTS.get(p, 0.5)
            for p, d in valid_platforms
        )
        overall_trend = "growing" if weighted_trend_score > 1.2 else "stable" if weighted_trend_score > 0.5 else "declining"

        # Calculate viability score (0-100) — improved formula
        # Job volume (0-30): log scale so 10 jobs ≈ 10, 1000 jobs ≈ 25, 5000+ ≈ 30
        import math
        job_score = min(30, int(10 * math.log10(max(total_jobs, 1) + 1)))

        # Rate potential (0-25): $10/hr = 2.5, $50/hr = 12.5, $100/hr = 25
        rate_score = min(25, int(weighted_rate / 4))

        # Trend bonus (0-15)
        trend_score = {"growing": 15, "stable": 8, "declining": 0}[overall_trend]

        # Platform diversity bonus (0-10): more platforms = more signal
        diversity_score = min(10, len(valid_platforms) * 3)

        # Base viability
        base_score = 20

        viability = min(100, job_score + rate_score + trend_score + diversity_score + base_score)

        # Build platform breakdown for storage
        platform_breakdown = {
            p: {"job_count": d.job_count, "avg_rate": d.avg_rate, "trend": d.trend}
            for p, d in valid_platforms
        }

        intelligence = TopicIntelligence(
            topic=slug,
            freelance_job_count=total_jobs,
            avg_rate=round(weighted_rate, 2),
            demand_trend=overall_trend,
            viability_score=viability,
            platform_breakdown=platform_breakdown,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

        # Upsert to topic_intelligence (source of truth for topic pages + search)
        row = {
            "topic": slug,
            "freelance_job_count": intelligence.freelance_job_count,
            "avg_rate": intelligence.avg_rate,
            "demand_trend": intelligence.demand_trend,
            "viability_score": intelligence.viability_score,
            "last_updated": intelligence.last_updated,
            "platform_breakdown": platform_breakdown,
            # Enrollment/placement metrics are computed elsewhere — don't clobber
        }
        try:
            sb.table("topic_intelligence").upsert(row, on_conflict="topic").execute()
        except Exception as e:
            # Older schemas without platform_breakdown column
            if "platform_breakdown" in str(e):
                row.pop("platform_breakdown", None)
                sb.table("topic_intelligence").upsert(row, on_conflict="topic").execute()
            else:
                raise

        # Keep topics table in sync so other readers see fresh numbers
        try:
            sb.table("topics").update({
                "job_count": intelligence.freelance_job_count,
                "avg_rate": intelligence.avg_rate,
                "demand_score": intelligence.viability_score,
            }).eq("slug", slug).execute()
        except Exception as e:
            logger.debug(f"topics table sync skipped for {slug}: {e}")

        logger.info(
            f"✅ {slug}: {total_jobs} jobs (weighted: {total_weighted_jobs:.0f}), "
            f"${weighted_rate:.0f}/hr, {overall_trend}, viability={viability}, "
            f"platforms={list(platform_breakdown.keys())}"
        )

        return intelligence

    except asyncio.TimeoutError:
        logger.error(f"Timeout scraping platforms for {slug}")
        return None
    except Exception as e:
        logger.error(f"Failed to refresh {slug}: {e}", exc_info=True)
        return None


async def refresh_all_topic_intelligence():
    """Refresh demand data for all curated topics from the database."""
    sb = get_supabase_service()
    topics = await fetch_curated_topics(sb)

    if not topics:
        logger.warning("No curated topics found in database")
        return

    logger.info(f"Starting demand refresh for {len(topics)} curated topics")

    # Process with controlled concurrency (max 3 at a time to avoid rate limits)
    semaphore = asyncio.Semaphore(3)

    async def refresh_with_semaphore(topic):
        async with semaphore:
            return await refresh_topic_intelligence(sb, topic)

    tasks = [refresh_with_semaphore(topic) for topic in topics]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = sum(1 for r in results if isinstance(r, TopicIntelligence))
    error_count = sum(1 for r in results if isinstance(r, Exception))
    none_count = sum(1 for r in results if r is None and not isinstance(r, Exception))

    logger.info(f"Demand refresh complete: {success_count} updated, {none_count} skipped, {error_count} errors")


if __name__ == "__main__":
    # Configure logging for standalone run
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    asyncio.run(refresh_all_topic_intelligence())