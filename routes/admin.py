"""
Admin routes — platform overview, user management, production monitoring
"""
from flask import Blueprint, render_template, redirect, url_for, flash, g, current_app
from services.supabase_client import get_supabase

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    """Simple admin check decorator."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.user:
            return redirect(url_for("auth.login"))
        # For MVP, first user is admin. In production, add admin flag to user_profiles
        email = g.user.get("email", "")
        if email != os.getenv("ADMIN_EMAIL", ""):
            flash("Admin access required", "error")
            return redirect(url_for("dashboard.home"))
        return f(*args, **kwargs)
    return decorated

import os


@admin_bp.route("/")
def dashboard():
    """Admin overview dashboard."""
    if not g.user:
        return redirect(url_for("auth.login"))
    
    sb = get_supabase()
    
    # Stats
    users_count = sb.table("user_profiles").select("id", count="exact").execute()
    cohorts_count = sb.table("cohorts").select("id", count="exact").execute()
    paid_count = sb.table("user_acquisition").select("id", count="exact") \
        .not_.is_("converted_to_paid_at", "null").execute()
    
    recent_signups = sb.table("user_acquisition").select("*") \
        .order("signed_up_at", desc=True).limit(10).execute()
    
    active_cohorts = sb.table("cohorts").select("*") \
        .eq("status", "active").execute()
    
    return render_template("admin/dashboard.html",
        users_count=getattr(users_count, 'count', 0) or 0,
        cohorts_count=getattr(cohorts_count, 'count', 0) or 0,
        paid_count=getattr(paid_count, 'count', 0) or 0,
        recent_signups=recent_signups.data or [],
        active_cohorts=active_cohorts.data or [],
    )


@admin_bp.route("/users")
def users():
    """View all users."""
    if not g.user:
        return redirect(url_for("auth.login"))
    
    sb = get_supabase()
    users = sb.table("user_profiles").select("*") \
        .order("created_at", desc=True).limit(50).execute()
    
    return render_template("admin/users.html", users=users.data or [])


@admin_bp.route("/production")
def production():
    """View video production queue and status."""
    if not g.user:
        return redirect(url_for("auth.login"))
    
    sb = get_supabase()
    
    pending = sb.table("cohort_videos").select("*") \
        .eq("production_status", "pending") \
        .order("day_number", asc=True).limit(20).execute()
    
    recent = sb.table("cohort_videos").select("*") \
        .order("created_at", desc=True).limit(20).execute()
    
    return render_template("admin/production.html",
        pending=pending.data or [],
        recent=recent.data or [],
        video_pipeline_dir=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "video-pipeline"),
    )


@admin_bp.route("/production/trigger/<video_id>", methods=["POST"])
def trigger_production(video_id):
    """Manually trigger video production for a specific cohort_video."""
    if not g.user:
        return redirect(url_for("auth.login"))
    
    sb = get_supabase()
    
    # Get the cohort_video
    cv = sb.table("cohort_videos").select("*, cohort:cohorts(*)").eq("id", video_id).limit(1).execute()
    if not cv.data:
        flash("Video record not found", "error")
        return redirect(url_for("admin.production"))
    
    video = cv.data[0]
    cohort = video.get("cohort", {})
    topic = cohort.get("topic_id", "unknown")
    
    # Get curriculum day info
    curriculum_day = None
    if video.get("curriculum_day_id"):
        cd = sb.table("curriculum_days").select("*").eq("id", video["curriculum_day_id"]).limit(1).execute()
        if cd.data:
            curriculum_day = cd.data[0]
    
    # Trigger async production in background
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
    
    flash(f"Production started for Day {video['day_number']} (background). Check back in ~10 min.", "info")
    return redirect(url_for("admin.production"))
