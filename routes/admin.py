"""
Admin routes — platform overview, user management, production monitoring
"""
import os
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, g, current_app
from services.supabase_client import get_supabase

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
logger = logging.getLogger(__name__)


@admin_bp.route("/")
def dashboard():
    """Admin overview dashboard."""
    if not g.user:
        return redirect(url_for("auth.login"))
    
    sb = get_supabase()
    
    try:
        users_resp = sb.table("user_profiles").select("id", count="exact").execute()
        users_count = getattr(users_resp, 'count', 0) or 0
    except Exception as e:
        logger.warning(f"Failed to count users: {e}")
        users_count = 0
    
    try:
        cohorts_resp = sb.table("cohorts").select("id", count="exact").execute()
        cohorts_count = getattr(cohorts_resp, 'count', 0) or 0
    except Exception as e:
        logger.warning(f"Failed to count cohorts: {e}")
        cohorts_count = 0
    
    try:
        paid_resp = sb.table("user_acquisition").select("id", count="exact").execute()
        paid_count = getattr(paid_resp, 'count', 0) or 0
    except Exception as e:
        logger.warning(f"Failed to count paid users: {e}")
        paid_count = 0
    
    try:
        signups_resp = sb.table("user_acquisition").select("*") \
            .order("signed_up_at", desc=True).limit(10).execute()
        recent_signups = signups_resp.data or []
    except Exception as e:
        logger.warning(f"Failed to get signups: {e}")
        recent_signups = []
    
    try:
        cohorts_resp = sb.table("cohorts").select("*") \
            .eq("status", "active").execute()
        active_cohorts = cohorts_resp.data or []
    except Exception as e:
        logger.warning(f"Failed to get cohorts: {e}")
        active_cohorts = []
    
    return render_template("admin/dashboard.html",
        users_count=users_count,
        cohorts_count=cohorts_count,
        paid_count=paid_count,
        recent_signups=recent_signups,
        active_cohorts=active_cohorts,
    )


@admin_bp.route("/users")
def users():
    """View all users."""
    if not g.user:
        return redirect(url_for("auth.login"))
    
    sb = get_supabase()
    try:
        users_resp = sb.table("user_profiles").select("*") \
            .order("created_at", desc=True).limit(50).execute()
        user_list = users_resp.data or []
    except Exception as e:
        logger.warning(f"Failed to list users: {e}")
        user_list = []
    
    return render_template("admin/users.html", users=user_list)


@admin_bp.route("/production")
def production():
    """View video production queue and status."""
    if not g.user:
        return redirect(url_for("auth.login"))
    
    sb = get_supabase()
    
    try:
        pending_resp = sb.table("cohort_videos").select("*") \
            .eq("production_status", "pending") \
            .order("day_number").limit(20).execute()
        pending = pending_resp.data or []
    except Exception as e:
        logger.warning(f"Failed to get pending: {e}")
        pending = []
    
    try:
        recent_resp = sb.table("cohort_videos").select("*") \
            .order("created_at", desc=True).limit(20).execute()
        recent = recent_resp.data or []
    except Exception as e:
        logger.warning(f"Failed to get recent: {e}")
        recent = []
    
    pipeline_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "video-pipeline")
    
    return render_template("admin/production.html",
        pending=pending,
        recent=recent,
        video_pipeline_dir=pipeline_dir,
    )


@admin_bp.route("/production/trigger/<video_id>", methods=["POST"])
def trigger_production(video_id):
    """Manually trigger video production for a specific cohort_video."""
    if not g.user:
        return redirect(url_for("auth.login"))
    
    sb = get_supabase()
    
    try:
        cv = sb.table("cohort_videos").select("*, cohort:cohorts(*)").eq("id", video_id).limit(1).execute()
        if not cv.data:
            flash("Video record not found", "error")
            return redirect(url_for("admin.production"))
        
        video = cv.data[0]
        cohort = video.get("cohort", {})
        topic = cohort.get("topic_id", "unknown")
        
        curriculum_day = None
        if video.get("curriculum_day_id"):
            cd = sb.table("curriculum_days").select("*").eq("id", video["curriculum_day_id"]).limit(1).execute()
            if cd.data:
                curriculum_day = cd.data[0]
        
        import threading
        from services.render_worker import produce_day_video
        
        def _produce():
            with current_app.app_context():
                produce_day_video(
                    cohort_video_id=video_id,
                    topic=topic.replace("-", " ").title(),
                    day_title=curriculum_day.get("video_title", f"Day {video['day_number']}") if curriculum_day else f"Day {video['day_number']}",
                    description=curriculum_day.get("description", "") if curriculum_day else "",
                )
        
        thread = threading.Thread(target=_produce, daemon=True)
        thread.start()
        
        flash(f"Production started for Day {video['day_number']}. Check back.", "info")
    except Exception as e:
        flash(f"Failed to start production: {e}", "error")
        logger.error(f"Trigger production error: {e}")
    
    return redirect(url_for("admin.production"))
