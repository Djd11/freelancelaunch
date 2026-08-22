"""
platform_scheduler — APScheduler-based cron for periodic job feed refresh.

Runs inside the Flask process. Each platform connection has its own
sync_interval_hours. The scheduler fires refresh_all_platforms() on
the configured interval, plus a manual trigger endpoint for admins.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_scheduler = None


def start_scheduler(app):
    """Start the APScheduler BackgroundScheduler (call once at app startup)."""
    global _scheduler
    if _scheduler is not None:
        return  # already running

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        logger.warning("APScheduler not installed — periodic refresh disabled")
        return

    _scheduler = BackgroundScheduler()

    def _refresh_job():
        """Periodic refresh — runs inside app context."""
        with app.app_context():
            try:
                from services.supabase_client import get_supabase
                from services.feed_ingest import refresh_all_platforms
                sb = get_supabase()
                results = refresh_all_platforms(sb)
                logger.info("Scheduled refresh: %s", results)
            except Exception as exc:
                logger.exception("Scheduled refresh failed: %s", exc)

    # Default: refresh every 6 hours
    _scheduler.add_job(
        _refresh_job,
        trigger=IntervalTrigger(hours=6),
        id="platform_refresh",
        name="Freelance platform feed refresh",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info("Platform scheduler started (6h interval)")


def stop_scheduler():
    """Stop the scheduler (call at app teardown)."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Platform scheduler stopped")


def trigger_refresh_now(app) -> dict:
    """Manually trigger an immediate refresh. Returns results dict."""
    with app.app_context():
        from services.supabase_client import get_supabase
        from services.feed_ingest import refresh_all_platforms
        sb = get_supabase()
        return refresh_all_platforms(sb)


def get_scheduler_status() -> dict:
    """Return scheduler status info."""
    if _scheduler is None:
        return {"running": False, "jobs": []}
    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        })
    return {"running": _scheduler.running, "jobs": jobs}
