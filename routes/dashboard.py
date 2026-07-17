"""
Dashboard routes — main user experience
"""
from flask import Blueprint, render_template, redirect, url_for, flash, g
from services.supabase_client import get_supabase

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
        pipeline=pipeline
    )


@dashboard_bp.route("/day/<int:day_number>")
def day_detail(day_number):
    """View a specific day's content."""
    if not g.user:
        return redirect(url_for("auth.login"))
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    profile_resp = sb.table("user_profiles").select("*").eq("user_id", user_id).limit(1).execute()
    profile = profile_resp.data[0] if profile_resp.data else {}
    cohort_id = profile.get("cohort_id")
    
    if not cohort_id:
        return redirect(url_for("topics.explore"))
    
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
    
    # Get user progress
    progress = None
    if video:
        prog_resp = sb.table("user_progress").select("*") \
            .eq("user_id", user_id) \
            .eq("cohort_video_id", video["id"]) \
            .limit(1) \
            .execute()
        progress = prog_resp.data[0] if prog_resp.data else None
    
    return render_template("dashboard/day.html",
        day_number=day_number,
        video=video,
        curriculum_day=curriculum_day,
        progress=progress
    )
