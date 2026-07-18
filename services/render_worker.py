"""
Render Worker — Full Pipeline Orchestrator
Script → TTS → PanelContent.js → Remotion Render → YouTube Upload
"""
import os
import subprocess
import json
import time
from flask import current_app
from services.supabase_client import get_supabase
from services.video_script_generator import generate_video_content
from services.panel_content_writer import write_panel_content, write_keywords
from services.youtube_uploader import upload_video, save_video_metadata

VIDEO_PIPELINE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "video-pipeline")


def produce_day_video(cohort_video_id: str, topic: str, day_title: str, description: str) -> dict:
    """
    Full production pipeline for a single day's video.
    Returns: { "status": "ready"|"failed", "youtube_url": "...", "error": "..." }
    """
    sb = get_supabase()
    
    try:
        # 1. Mark as scripting
        _update_status(sb, cohort_video_id, "scripting")
        
        # 2. Generate script + panels
        content = generate_video_content(topic, day_title, description)
        script = content["script"]
        panels = content["panels"]
        
        # 3. Generate TTS audio
        _update_status(sb, cohort_video_id, "rendering")
        audio_path = _generate_tts(script)
        if not audio_path:
            raise Exception("TTS generation failed")
        
        # 4. Write PanelContent.js
        pipeline_dir = _get_pipeline_dir()
        if not pipeline_dir:
            raise Exception("Video pipeline directory not found")
        
        write_panel_content(panels, pipeline_dir)
        
        # 5. Copy audio to pipeline
        dest_audio = os.path.join(pipeline_dir, "public", "audio", "narration.mp3")
        os.makedirs(os.path.dirname(dest_audio), exist_ok=True)
        subprocess.run(["cp", audio_path, dest_audio], check=True)
        
        # 6. Render video
        _update_status(sb, cohort_video_id, "rendering")
        video_path = _render_video(pipeline_dir)
        if not video_path:
            raise Exception("Video rendering failed")
        
        # 7. Upload to YouTube
        _update_status(sb, cohort_video_id, "uploading")
        yt_title = f"{day_title} — {topic}"
        yt_desc = f"Learn {topic} with FreelanceLaunch. Day-by-day curriculum to build your freelance skills.\n\nJoin FreelanceLaunch: https://freelancelaunch.onrender.com"
        
        upload_result = upload_video(video_path, yt_title, yt_desc)
        
        # 8. Update DB with result
        _update_status(sb, cohort_video_id, "ready", {
            "youtube_url": upload_result.get("url", ""),
            "youtube_video_id": upload_result.get("video_id", ""),
            "youtube_title": yt_title,
            "local_path": video_path,
            "aired_at": "now()",
        })
        
        return {"status": "ready", "youtube_url": upload_result.get("url", "")}
    
    except Exception as e:
        error_msg = str(e)
        _update_status(sb, cohort_video_id, "failed", {"error_message": error_msg})
        return {"status": "failed", "error": error_msg}


def _generate_tts(script: str) -> str:
    """Generate TTS audio file using edge-tts."""
    output_path = f"/tmp/fl_tts_{int(time.time())}.mp3"
    
    result = subprocess.run(
        ["edge-tts", "--voice", "en-US-ChristopherNeural", "--text", script,
         "--write-media", output_path],
        capture_output=True, text=True, timeout=120
    )
    
    if result.returncode != 0 or not os.path.exists(output_path):
        return None
    
    return output_path


def _render_video(pipeline_dir: str) -> str:
    """Run Remotion render."""
    output_path = os.path.join(pipeline_dir, "out", "video-final.mp4")
    os.makedirs(os.path.join(pipeline_dir, "out"), exist_ok=True)
    
    result = subprocess.run(
        ["npx", "remotion", "render", "src/index.js", "TwoPanel", output_path, "--overwrite"],
        cwd=pipeline_dir,
        capture_output=True, text=True, timeout=7200  # 2 hour timeout for slow hardware
    )
    
    if result.returncode != 0 or not os.path.exists(output_path):
        return None
    
    return output_path


def _get_pipeline_dir() -> str:
    """Get or create the video pipeline directory."""
    paths = [
        VIDEO_PIPELINE_DIR,
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "video-pipeline"),
    ]
    
    for p in paths:
        if os.path.exists(os.path.join(p, "package.json")):
            return os.path.abspath(p)
    
    return None


def _update_status(sb, cohort_video_id: str, status: str, extra: dict = None):
    """Update cohort_video production status in DB."""
    data = {"production_status": status}
    if extra:
        data.update(extra)
    
    # Also log the production step
    sb.table("cohort_videos").update(data).eq("id", cohort_video_id).execute()
    sb.table("video_production_log").insert({
        "cohort_video_id": cohort_video_id,
        "step": status,
        "status": "completed" if status in ("ready",) else "running",
        "started_at": "now()",
    }).execute()
