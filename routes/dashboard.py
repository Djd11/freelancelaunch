"""
Dashboard routes — main user experience
"""
import logging
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, g, request
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
    cohort_resp = sb.table("cohorts").select("*,topics(slug,name)").eq("id", cohort_id).limit(1).execute()
    cohort = cohort_resp.data[0] if cohort_resp.data else None
    if not cohort:
        flash("Cohort not found", "error")
        return redirect(url_for("topics.explore"))

    # ── Resolve the active topic: prefer selected_topic_id over cohort topic ──
    selected_topic_id = profile.get("selected_topic_id")
    active_topic_slug = None
    active_topic_name = None

    if selected_topic_id:
        try:
            tdb = sb.table("topics").select("id,name,slug").eq("id", selected_topic_id).limit(1).execute()
            if tdb.data:
                active_topic_slug = tdb.data[0].get("slug")
                active_topic_name = tdb.data[0].get("name")
        except Exception:
            pass

    # Fallback to cohort's topic
    if not active_topic_slug and cohort.get("topics"):
        active_topic_slug = cohort["topics"].get("slug")
        active_topic_name = cohort["topics"].get("name")
    elif not active_topic_slug and cohort.get("topic_id"):
        try:
            tdb = sb.table("topics").select("slug,name").eq("id", cohort["topic_id"]).limit(1).execute()
            if tdb.data:
                active_topic_slug = tdb.data[0].get("slug")
                active_topic_name = tdb.data[0].get("name")
        except Exception:
            pass

    current_day = cohort.get("current_day", 0)

    # ── Get curriculum day from the active topic (not just the cohort) ─────
    curriculum_day = None
    today_video = None

    # Try to find curriculum from the active topic first
    if active_topic_slug:
        try:
            tdb = sb.table("topics").select("id").eq("slug", active_topic_slug).limit(1).execute()
            if tdb.data:
                cur = sb.table("curricula").select("id").eq("topic_id", tdb.data[0]["id"]).limit(1).execute()
                if cur.data:
                    cd_resp = sb.table("curriculum_days").select("*") \
                        .eq("curriculum_id", cur.data[0]["id"]) \
                        .eq("day_number", current_day) \
                        .limit(1) \
                        .execute()
                    curriculum_day = cd_resp.data[0] if cd_resp.data else None
        except Exception as e:
            logger.warning(f"Dashboard curriculum lookup error: {e}")

    # Also try to find a matching cohort_video for this topic
    if active_topic_slug:
        try:
            # Find cohort for this topic
            topic_cohort = sb.table("cohorts").select("id") \
                .eq("topic_id", tdb.data[0]["id"] if tdb and tdb.data else "").limit(1).execute()
            if topic_cohort.data:
                vid_resp = sb.table("cohort_videos").select("*") \
                    .eq("cohort_id", topic_cohort.data[0]["id"]) \
                    .eq("day_number", current_day) \
                    .limit(1).execute()
                today_video = vid_resp.data[0] if vid_resp.data else None
        except Exception:
            pass

    # Fallback: use cohort's video if no topic-specific video found
    if not today_video:
        video_resp = sb.table("cohort_videos").select("*") \
            .eq("cohort_id", cohort_id) \
            .eq("day_number", current_day) \
            .limit(1) \
            .execute()
        today_video = video_resp.data[0] if video_resp.data else None

    # Fallback: use cohort's curriculum if no topic-specific curriculum found
    if not curriculum_day and today_video and today_video.get("curriculum_day_id"):
        cd_resp = sb.table("curriculum_days").select("*") \
            .eq("id", today_video["curriculum_day_id"]) \
            .limit(1) \
            .execute()
        curriculum_day = cd_resp.data[0] if cd_resp.data else None

    # Get user's progress for today
    progress = None
    if today_video:
        prog_resp = sb.table("user_progress").select("*") \
            .eq("user_id", user_id) \
            .eq("cohort_video_id", today_video["id"]) \
            .limit(1) \
            .execute()
        progress = prog_resp.data[0] if prog_resp.data else None

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
        day_celebrated=day_celebrated,
        active_topic_slug=active_topic_slug,
        active_topic_name=active_topic_name,
    )


@dashboard_bp.route("/day/<int:day_number>")
def day_detail(day_number):
    """View a specific day's content. Auto-generates curriculum if missing (never 500).

    Supports ?topic=<slug> for TOPIC-SCOPED day views (used by the /topics/<slug>
    detail page day links). When present, the lesson resolves from THAT topic's
    curriculum — never from the user's cohort — so browsing n8n day 1 can never
    show a Shopify lesson even if the user's enrolled cohort is Shopify.
    Progress checkboxes only appear when the user's cohort topic matches.
    """
    if not g.user:
        return redirect(url_for("auth.login"))

    sb = get_supabase()
    user_id = g.user["id"]
    topic_param = (request.args.get("topic") or "").strip() or None

    profile_resp = sb.table("user_profiles").select("*").eq("user_id", user_id).limit(1).execute()
    profile = profile_resp.data[0] if profile_resp.data else {}
    cohort_id = profile.get("cohort_id")

    if not cohort_id and not topic_param:
        return redirect(url_for("topics.explore"))

    # ── Cohort context (may be absent for topic-scoped browsing) ──────────
    cohort = {}
    cohort_topic_slug = None
    if cohort_id:
        cohort_resp = sb.table("cohorts").select("*,topics(slug,name)").eq("id", cohort_id).limit(1).execute()
        cohort = cohort_resp.data[0] if cohort_resp.data else {}
        if cohort.get("topics"):
            cohort_topic_slug = cohort["topics"].get("slug")
        elif cohort.get("topic_id"):
            try:
                tdb = sb.table("topics").select("slug,name").eq("id", cohort["topic_id"]).limit(1).execute()
                if tdb.data:
                    cohort_topic_slug = tdb.data[0].get("slug")
            except Exception as e:
                print(f"Topic fallback lookup error: {e}")

    # ── Which topic does this day belong to? ───────────────────────────────
    is_topic_scoped = bool(topic_param)
    topic_slug = topic_param or cohort_topic_slug
    topic_name = None
    if topic_slug:
        try:
            tdb = sb.table("topics").select("name").eq("slug", topic_slug).limit(1).execute()
            if tdb.data:
                topic_name = tdb.data[0].get("name")
        except Exception as e:
            print(f"Topic name lookup error: {e}")

    # ── Cohort video only when the cohort topic matches the viewed topic ───
    video = None
    if cohort_id and cohort_topic_slug == topic_slug:
        video_resp = sb.table("cohort_videos").select("*") \
            .eq("cohort_id", cohort_id) \
            .eq("day_number", day_number) \
            .limit(1) \
            .execute()
        video = video_resp.data[0] if video_resp.data else None

    # ── Curriculum day (from the topic's curriculum, cohort-agnostic) ──────
    curriculum_day = None
    if video and video.get("curriculum_day_id"):
        cd_resp = sb.table("curriculum_days").select("*") \
            .eq("id", video["curriculum_day_id"]) \
            .limit(1) \
            .execute()
        curriculum_day = cd_resp.data[0] if cd_resp.data else None

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

    # ── User progress ───────────────────────────────────────────────────────
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

    # Check if content is fallback-quality (for "Regenerate" button)
    is_fallback = False
    if curriculum_day:
        from services.curriculum_generator import is_fallback_content
        is_fallback = is_fallback_content(curriculum_day)

    return render_template("dashboard/day.html",
        day_number=day_number,
        video=video,
        curriculum_day=curriculum_day,
        progress=progress,
        needs_generation=needs_generation,
        topic_slug=topic_slug,
        topic_name=topic_name,
        cohort=cohort,
        is_topic_scoped=is_topic_scoped,
        is_fallback_content=is_fallback
    )
