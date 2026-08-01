"""
Video Preview routes — serve HTML TwoPanel previews with voiceover for curriculum days
"""
import logging
import os
from flask import Blueprint, render_template_string, g, redirect, url_for, abort, Response

logger = logging.getLogger(__name__)
preview_bp = Blueprint("preview", __name__, url_prefix="/preview")

# Local cache dir for generated audio
AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "previews")


def _ensure_audio_dir():
    os.makedirs(AUDIO_DIR, exist_ok=True)


def _get_curriculum_day(sb, user_id, cohort_id, day_number):
    """Get curriculum day for a user's cohort."""
    # Try cohort_videos → curriculum_day_id
    video_resp = sb.table("cohort_videos").select("*") \
        .eq("cohort_id", cohort_id).eq("day_number", day_number).limit(1).execute()
    video = video_resp.data[0] if video_resp.data else None

    if video and video.get("curriculum_day_id"):
        cd = sb.table("curriculum_days").select("*").eq("id", video["curriculum_day_id"]).limit(1).execute()
        if cd.data:
            return cd.data[0], video

    # Fallback: cohort's curriculum by day_number
    cohort_resp = sb.table("cohorts").select("curriculum_id").eq("id", cohort_id).limit(1).execute()
    if cohort_resp.data and cohort_resp.data[0].get("curriculum_id"):
        cid = cohort_resp.data[0]["curriculum_id"]
        cd = sb.table("curriculum_days").select("*") \
            .eq("curriculum_id", cid).eq("day_number", day_number).limit(1).execute()
        if cd.data:
            return cd.data[0], video
    return None, video


@preview_bp.route("/day/<int:day_number>")
def day_preview(day_number):
    """Serve the HTML TwoPanel video preview for a curriculum day."""
    if not g.user:
        return redirect(url_for("auth.login"))

    from services.supabase_client import get_supabase
    sb = get_supabase()
    user_id = g.user["id"]

    profile_resp = sb.table("user_profiles").select("cohort_id").eq("user_id", user_id).limit(1).execute()
    cohort_id = profile_resp.data[0]["cohort_id"] if profile_resp.data else None

    if not cohort_id:
        return redirect(url_for("topics.explore"))

    curriculum_day, video = _get_curriculum_day(sb, user_id, cohort_id, day_number)
    if not curriculum_day:
        abort(404, description="Curriculum day not found")

    # Build voiceover script
    from services.preview_generator import (
        build_voiceover_text, generate_tts, get_audio_duration,
        extract_keywords, build_preview_html
    )
    script = build_voiceover_text(curriculum_day)
    title = curriculum_day.get("title", f"Day {day_number}")

    # Generate TTS audio (cached)
    _ensure_audio_dir()
    audio_path = os.path.join(AUDIO_DIR, f"day_{day_number}.mp3")
    audio_url = f"/static/previews/day_{day_number}.mp3"

    if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1000:
        logger.info(f"Generating TTS for day {day_number}...")
        ok = generate_tts(script, audio_path)
        if not ok:
            logger.warning(f"TTS failed for day {day_number}, using silent fallback")
            audio_url = ""  # No audio — kinetic text still works

    duration = get_audio_duration(audio_path) if os.path.exists(audio_path) else 20.0

    # Accent color from day number (rotating palette)
    palette = ["#6366f1", "#eab308", "#22c55e", "#ec4899", "#06b6d4", "#f97316", "#8b5cf6"]
    color = palette[day_number % len(palette)]

    keywords = extract_keywords(script)
    html = build_preview_html(day_number, title, script, audio_url, color, keywords, duration)

    return Response(html, mimetype="text/html")
