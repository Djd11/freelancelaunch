"""
Scheduler — Finds cohorts needing video production and queues the work
Run this via cron or systemd timer at 2 AM daily
"""
import os
import sys
import logging

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app import create_app
from services.supabase_client import get_supabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler")


def run_nightly_production():
    """
    Find all active cohorts and produce the next day's video.
    Run this at 2 AM daily via cron.
    """
    app = create_app()
    
    with app.app_context():
        sb = get_supabase()
        
        # 1. Find all active cohorts
        cohorts = sb.table("cohorts").select("*") \
            .eq("status", "active") \
            .execute()
        
        if not cohorts.data:
            logger.info("No active cohorts found")
            return
        
        logger.info(f"Found {len(cohorts.data)} active cohorts")
        
        for cohort in cohorts.data:
            cohort_id = cohort["id"]
            current_day = cohort.get("current_day", 0)
            max_days = cohort.get("max_days", 30)
            topic = cohort.get("topic_id", "unknown")
            
            # Calculate tomorrow's day
            tomorrow_day = current_day + 1
            
            if tomorrow_day > max_days:
                logger.info(f"Cohort {cohort_id}: already completed ({current_day}/{max_days})")
                continue
            
            # 2. Check if video already exists for tomorrow
            existing = sb.table("cohort_videos").select("id, production_status") \
                .eq("cohort_id", cohort_id) \
                .eq("day_number", tomorrow_day) \
                .limit(1) \
                .execute()
            
            if existing.data:
                status = existing.data[0].get("production_status")
                if status == "ready":
                    logger.info(f"Cohort {cohort_id}: Day {tomorrow_day} already ready")
                    continue
                if status == "rendering":
                    logger.info(f"Cohort {cohort_id}: Day {tomorrow_day} already rendering")
                    continue
            
            # 3. Get curriculum info for this day
            curriculum = sb.table("curricula").select("id") \
                .eq("topic_id", topic) \
                .limit(1) \
                .execute()
            
            if not curriculum.data:
                logger.warning(f"Cohort {cohort_id}: No curriculum found for topic {topic}")
                continue
            
            curriculum_id = curriculum.data[0]["id"]
            
            curriculum_day = sb.table("curriculum_days").select("*") \
                .eq("curriculum_id", curriculum_id) \
                .eq("day_number", tomorrow_day) \
                .limit(1) \
                .execute()
            
            day_info = curriculum_day.data[0] if curriculum_day.data else None
            
            # 4. Create or get cohort_video record
            cohort_video_id = None
            if existing.data:
                cohort_video_id = existing.data[0]["id"]
            else:
                cv = sb.table("cohort_videos").insert({
                    "cohort_id": cohort_id,
                    "curriculum_day_id": day_info["id"] if day_info else None,
                    "day_number": tomorrow_day,
                    "youtube_title": day_info.get("video_title", f"Day {tomorrow_day}") if day_info else f"Day {tomorrow_day}",
                    "production_status": "pending",
                }).execute()
                cohort_video_id = cv.data[0]["id"]
            
            if not cohort_video_id:
                logger.error(f"Cohort {cohort_id}: Failed to create video record")
                continue
            
            # 5. Produce the video
            logger.info(f"Producing video for cohort {cohort_id}, day {tomorrow_day}")
            
            from services.render_worker import produce_day_video
            
            topic_name = topic.replace("-", " ").title()
            day_title = day_info.get("video_title", f"Day {tomorrow_day}: {topic_name}") if day_info else f"Day {tomorrow_day}: {topic_name}"
            description = day_info.get("description", "") if day_info else ""
            
            result = produce_day_video(
                cohort_video_id=cohort_video_id,
                topic=topic_name,
                day_title=day_title,
                description=description
            )
            
            if result["status"] == "ready":
                logger.info(f"✅ Day {tomorrow_day} video ready: {result.get('youtube_url', 'N/A')}")
            else:
                logger.error(f"❌ Day {tomorrow_day} failed: {result.get('error', 'Unknown')}")


if __name__ == "__main__":
    run_nightly_production()
