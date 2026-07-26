"""
Generate Curriculum API — day-by-day generation with real-time progress
"""
import logging
import os
import threading
from flask import Blueprint, jsonify, g
from services.supabase_client import get_supabase
from services.curriculum_generator import generate_curriculum

logger = logging.getLogger(__name__)
gen_bp = Blueprint("generate", __name__, url_prefix="/api")

# In-memory progress tracker (for MVP — use DB table for production)
_progress_tracker = {}


def _get_llm_config():
    """Get LLM API configuration — tries multiple providers in order."""
    # Priority 1: Environment variables (set on Render)
    api_url = os.environ.get("LLM_API_URL", "")
    api_key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "")
    
    # Priority 2: OpenRouter from vision-tool config
    if not api_key:
        try:
            import json
            with open(os.path.expanduser("~/Documents/vision-tool/config.json")) as f:
                vc = json.load(f)
            api_key = vc.get("OPENROUTER_API_KEY", "")
            api_url = "https://openrouter.ai/api/v1/chat/completions"
            model = "google/gemma-4-26b-a4b-it:free"
        except Exception:
            pass
    
    # Priority 3: Hermes config (OpenCode.ai)
    if not api_key:
        try:
            import yaml
            with open(os.path.expanduser("~/.hermes/config.yaml")) as f:
                hermes = yaml.safe_load(f)
            model_cfg = hermes.get("model", {})
            api_key = model_cfg.get("api_key", "")
            api_url = model_cfg.get("base_url", "") + "/chat/completions"
            model = model_cfg.get("default", "gpt-4o-mini")
        except Exception:
            pass
    
    return api_url, api_key, model


@gen_bp.route("/generate-curriculum/<slug>", methods=["POST"])
def generate_curriculum_api(slug):
    """Generate curriculum day-by-day. Frontend polls /status for progress."""
    if not g.user:
        return jsonify({"status": "error", "error": "Not logged in"}), 401
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    # Verify enrollment
    pipeline = sb.table("freelance_pipeline").select("id") \
        .eq("user_id", user_id).eq("topic", slug).limit(1).execute()
    if not pipeline.data:
        return jsonify({"status": "error", "error": "You must enroll first"}), 400
    
    # Get topic info
    from routes.topics import CURATED_TOPICS
    topic = next((t for t in CURATED_TOPICS if t["slug"] == slug), None)
    topic_name = topic["name"] if topic else slug.replace("-", " ").title()
    
    topic_db = sb.table("topics").select("id").eq("slug", slug).limit(1).execute()
    if not topic_db.data:
        return jsonify({"status": "error", "error": "Topic not found"}), 404
    
    topic_id = topic_db.data[0]["id"]
    
    # Get or create curriculum record
    curr_resp = sb.table("curricula").select("id").eq("topic_id", topic_id).limit(1).execute()
    if curr_resp.data:
        curr_id = curr_resp.data[0]["id"]
        existing = sb.table("curriculum_days").select("id", count="exact") \
            .eq("curriculum_id", curr_id).execute()
        if getattr(existing, 'count', 0) or 0 >= 30:
            return jsonify({"status": "complete", "message": "Already generated"})
    else:
        curr = sb.table("curricula").insert({"topic_id": topic_id, "total_days": 30}).execute()
        curr_id = curr.data[0]["id"]
    
    # Get linked platforms
    linked_platforms = []
    try:
        plat = sb.table("user_platforms").select("platform") \
            .eq("user_id", user_id).eq("status", "verified").execute()
        linked_platforms = [p["platform"] for p in (plat.data or [])]
    except Exception:
        pass
    
    # Initialize progress
    _progress_tracker[slug] = {
        "status": "generating",
        "current_day": 0,
        "total_days": 30,
        "topic": topic_name,
    }
    
    # Start background generation
    thread = threading.Thread(
        target=_generate_in_background,
        args=(slug, curr_id, topic_name, 30, linked_platforms),
        daemon=True
    )
    thread.start()
    
    return jsonify({
        "status": "started",
        "message": f"Generating 30-day curriculum for {topic_name}"
    })


@gen_bp.route("/generation-status/<slug>")
def generation_status(slug):
    """Poll this endpoint to get real-time generation progress."""
    progress = _progress_tracker.get(slug, {"status": "unknown", "current_day": 0, "total_days": 30})
    return jsonify(progress)


def _generate_in_background(slug, curr_id, topic_name, total_days, linked_platforms):
    """Generate curriculum day-by-day in background thread."""
    try:
        # Get LLM config
        api_url, api_key, model = _get_llm_config()
        
        # Set config in app context
        import flask
        from app import create_app
        app = create_app()
        
        with app.app_context():
            flask.current_app.config["LLM_API_URL"] = api_url
            flask.current_app.config["LLM_API_KEY"] = api_key
            flask.current_app.config["LLM_MODEL"] = model
            
            # Generate all days at once (the generator already returns 30 days)
            curriculum = generate_curriculum(topic_name, total_days, platforms=linked_platforms)
            
            if not curriculum:
                _progress_tracker[slug] = {"status": "error", "error": "Generation returned empty"}
                return
            
            # Save days one by one, updating progress after each
            sb = get_supabase()
            
            # Get the user's cohort
            user_profile = sb.table("user_profiles").select("cohort_id").eq("user_id", user_id).limit(1).execute()
            cohort_id = user_profile.data[0]["cohort_id"] if user_profile.data else None
            
            for i, day in enumerate(curriculum):
                try:
                    # Pack 6-section format into existing columns
                    hook = day.get("hook", "")
                    concept = day.get("concept", day.get("description", ""))
                    practice = day.get("practice", day.get("practice_task", ""))
                    retrieval = day.get("retrieval", "")
                    spaced = day.get("spaced_review", "")
                    preview_text = day.get("preview", "")
                    
                    full_description = f"{hook}\n\n{concept}" if hook else concept
                    full_practice = f"{practice}\n\n## Retrieval\n{retrieval}" if retrieval else practice
                    full_apply = f"{spaced}\n\n{preview_text}" if spaced else preview_text
                    
                    day_data = {
                        "curriculum_id": curr_id,
                        "day_number": i + 1,
                        "title": day.get("title", f"Day {i + 1}"),
                        "description": full_description[:2000],
                        "learning_objectives": hook[:500],
                        "practice_task": full_practice[:2000],
                        "apply_task": full_apply[:1000],
                        "video_title": day.get("video_title", f"{topic_name} — Day {i + 1}"),
                    }
                    sb.table("curriculum_days").insert(day_data).execute()
                    
                    # Also create cohort_video entry so day detail links work
                    if cohort_id:
                        existing_video = sb.table("cohort_videos").select("id") \
                            .eq("cohort_id", cohort_id).eq("day_number", i+1).limit(1).execute()
                        if not existing_video.data:
                            sb.table("cohort_videos").insert({
                                "cohort_id": cohort_id,
                                "day_number": i + 1,
                                "youtube_title": day.get("video_title", f"{topic_name} — Day {i + 1}"),
                                "production_status": "ready",
                            }).execute()
                except Exception as e:
                    logger.warning(f"Failed to save day {i+1}: {e}")
                
                # Update progress after each day
                _progress_tracker[slug] = {
                    "status": "generating",
                    "current_day": i + 1,
                    "total_days": total_days,
                    "percent": round((i + 1) / total_days * 100),
                    "last_title": day.get("title", f"Day {i + 1}"),
                }
            
            # Mark complete
            _progress_tracker[slug] = {
                "status": "complete",
                "current_day": total_days,
                "total_days": total_days,
                "percent": 100,
                "last_title": "Complete!",
            }
            
            logger.info(f"Saved {total_days} curriculum days for {topic_name}")
    
    except Exception as e:
        logger.error(f"Background generation failed: {e}")
        _progress_tracker[slug] = {"status": "error", "error": str(e)}
