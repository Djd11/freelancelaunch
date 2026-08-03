"""
Dashboard routes — main user experience
"""
import logging
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, g
from services.supabase_client import get_supabase

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/")
def home():
    if not g.user:
        return redirect(url_for("auth.login", next=url_for("dashboard.home")))
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    # Get user profile
    profile_resp = sb.table("user_profiles").select("*").eq("user_id", user_id).limit(1).execute()
    profile = profile_resp.data[0] if profile_resp.data else {}
    
    cohort_id = profile.get("cohort_id")
    if not cohort_id:
        # No cohort assigned — redirect to topic selection
        return redirect(url_for("topics.explore"))
    
    # Get cohort info
    cohort_resp = sb.table("cohorts").select("*").eq("id", cohort_id).limit(1).execute()
    cohort = cohort_resp.data[0] if cohort_resp.data else None
    if not cohort:
        flash("Cohort not found", "error")
        return redirect(url_for("topics.explore"))
    
    current_day = cohort.get("current_day", 0)
    
    # Get today's video (cohort_videos for current day)
    video_resp = sb.table("cohort_videos").select("*") \
        .eq("cohort_id", cohort_id) \
        .eq("day_number", current_day) \
        .limit(1) \
        .execute()
    today_video = video_resp.data[0] if video_resp.data else None
    
    # Get user's progress for today
    progress = None
    if today_video:
        prog_resp = sb.table("user_progress").select("*") \
            .eq("user_id", user_id) \
            .eq("cohort_video_id", today_video["id"]) \
            .limit(1) \
            .execute()
        progress = prog_resp.data[0] if prog_resp.data else None
    
    # Get curriculum day info
    curriculum_day = None
    if today_video and today_video.get("curriculum_day_id"):
        cd_resp = sb.table("curriculum_days").select("*") \
            .eq("id", today_video["curriculum_day_id"]) \
            .limit(1) \
            .execute()
        curriculum_day = cd_resp.data[0] if cd_resp.data else None
    
    # Get overall progress stats
    days_completed = sb.table("user_progress").select("id", count="exact") \
        .eq("user_id", user_id) \
        .eq("video_watched", True) \
        .execute()
    total_done = days_completed.count if hasattr(days_completed, 'count') else 0
    
    # ─── CONFIDENCE ENGINE: streak, nudges, encouragement ─────
    try:
        from services.nudge_engine import (
            compute_streak, get_nudges, compute_confidence,
            get_milestone, get_encouragement, get_welcome_back
        )
        
        # Fetch all user progress to compute streak and nudges
        all_prog = sb.table("user_progress").select("day_number,video_watched,practice_completed,apply_completed,updated_at") \
            .eq("user_id", user_id).execute()
        prog_rows = all_prog.data or []
        
        # Completed dates (based on updated_at)
        completed_dates = []
        progress_days = {}
        last_completed_day = 0
        for row in prog_rows:
            day_num = row.get("day_number")
            progress_days[day_num] = row
            if row.get("video_watched") or row.get("practice_completed"):
                if row.get("updated_at"):
                    try:
                        completed_dates.append(datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")).date())
                    except Exception:
                        pass
                if day_num and day_num > last_completed_day:
                    last_completed_day = day_num
        
        streak = compute_streak(completed_dates)
        nudges = get_nudges(progress_days, last_completed_day, current_day)
        confidence = compute_confidence(total_done, streak, cohort.get("max_days", 30))
        milestone = get_milestone(current_day, streak)
        
        # Welcome-back nudge for inactive users
        welcome_back = None
        if last_completed_day > 0 and last_completed_day < current_day - 1:
            welcome_back = get_welcome_back(current_day - last_completed_day, current_day)
        
        # Today's celebration if all 3 done
        day_celebrated = False
        if progress and progress.get("video_watched") and progress.get("practice_completed") and progress.get("apply_completed"):
            day_celebrated = True
    except Exception as e:
        logger.error(f"Nudge engine error: {e}")
        streak, nudges, confidence, milestone = 0, [], {"score": 0, "level": "Day One", "message": ""}, None
        welcome_back, day_celebrated = None, False
    
    # Get freelance pipeline stats
    pipeline_resp = sb.table("freelance_pipeline").select("*") \
        .eq("user_id", user_id) \
        .limit(1) \
        .execute()
    pipeline = pipeline_resp.data[0] if pipeline_resp.data else None
    
    return render_template("dashboard/home.html",
        profile=profile,
        cohort=cohort,
        current_day=current_day,
        today_video=today_video,
        curriculum_day=curriculum_day,
        progress=progress,
        total_done=total_done,
        pipeline=pipeline,
        streak=streak,
        nudges=nudges,
        confidence=confidence,
        milestone=milestone,
        welcome_back=welcome_back,
        day_celebrated=day_celebrated
    )


@dashboard_bp.route("/day/<int:day_number>")
def day_detail(day_number):
    """View a specific day's content. Auto-generates curriculum if missing (never 500)."""
    if not g.user:
        return redirect(url_for("auth.login"))
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    profile_resp = sb.table("user_profiles").select("*").eq("user_id", user_id).limit(1).execute()
    profile = profile_resp.data[0] if profile_resp.data else {}
    cohort_id = profile.get("cohort_id")
    
    if not cohort_id:
        return redirect(url_for("topics.explore"))
    
    # Get cohort + topic slug (for curriculum generation)
    cohort_resp = sb.table("cohorts").select("*,topics(slug,name)").eq("id", cohort_id).limit(1).execute()
    cohort = cohort_resp.data[0] if cohort_resp.data else {}
    topic_slug = None
    topic_name = None
    if cohort.get("topics"):
        topic_slug = cohort["topics"].get("slug")
        topic_name = cohort["topics"].get("name")
    # Fallback when the topics join is blocked/empty (anon key RLS): resolve by topic_id
    if not topic_slug and cohort.get("topic_id"):
        try:
            tdb = sb.table("topics").select("slug,name").eq("id", cohort["topic_id"]).limit(1).execute()
            if tdb.data:
                topic_slug = tdb.data[0].get("slug")
                topic_name = tdb.data[0].get("name")
        except Exception as e:
            print(f"Topic fallback lookup error: {e}")
    
    # Get video for this day
    video_resp = sb.table("cohort_videos").select("*") \
        .eq("cohort_id", cohort_id) \
        .eq("day_number", day_number) \
        .limit(1) \
        .execute()
    video = video_resp.data[0] if video_resp.data else None
    
    # Get curriculum day
    curriculum_day = None
    if video and video.get("curriculum_day_id"):
        cd_resp = sb.table("curriculum_days").select("*") \
            .eq("id", video["curriculum_day_id"]) \
            .limit(1) \
            .execute()
        curriculum_day = cd_resp.data[0] if cd_resp.data else None
    
    # Fallback: get curriculum day by day_number from the cohort's curriculum
    if not curriculum_day and cohort.get("curriculum_id"):
        try:
            cid = cohort["curriculum_id"]
            cd_resp = sb.table("curriculum_days").select("*") \
                .eq("curriculum_id", cid) \
                .eq("day_number", day_number) \
                .limit(1) \
                .execute()
            curriculum_day = cd_resp.data[0] if cd_resp.data else None
        except Exception as e:
            print(f"Curriculum day fallback error: {e}")

    # Fallback 2: cohort.curriculum_id may be NULL even though a curriculum
    # EXISTS for this topic (cohort_videos.curriculum_day_id also null).
    # Resolve topic → curricula → curriculum_days by day_number so day links
    # render real content instead of spinning forever on the generation state.
    if not curriculum_day and topic_slug:
        try:
            tdb = sb.table("topics").select("id").eq("slug", topic_slug).limit(1).execute()
            if tdb.data:
                cur = sb.table("curricula").select("id") \
                    .eq("topic_id", tdb.data[0]["id"]).limit(1).execute()
                if cur.data:
                    cd_resp = sb.table("curriculum_days").select("*") \
                        .eq("curriculum_id", cur.data[0]["id"]) \
                        .eq("day_number", day_number) \
                        .limit(1) \
                        .execute()
                    curriculum_day = cd_resp.data[0] if cd_resp.data else None
        except Exception as e:
            print(f"Curriculum day fallback-2 error: {e}")
    
    # Get user progress
    progress = None
    if video:
        prog_resp = sb.table("user_progress").select("*") \
            .eq("user_id", user_id) \
            .eq("cohort_video_id", video["id"]) \
            .limit(1) \
            .execute()
        progress = prog_resp.data[0] if prog_resp.data else None
    
    # NEEDS GENERATION: curriculum missing — show loading state, auto-trigger generation
    needs_generation = curriculum_day is None
    if needs_generation and not topic_slug:
        # No topic context — fail gracefully, not 500
        flash("No curriculum available for this topic yet", "error")
        return redirect(url_for("dashboard.home"))
    
    return render_template("dashboard/day.html",
        day_number=day_number,
        video=video,
        curriculum_day=curriculum_day,
        progress=progress,
        needs_generation=needs_generation,
        topic_slug=topic_slug,
        topic_name=topic_name,
        cohort=cohort
    )
