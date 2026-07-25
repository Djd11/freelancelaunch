"""
Generate Curriculum API — on-demand curriculum generation with progress
"""
import logging
from flask import Blueprint, jsonify, g, current_app
from services.supabase_client import get_supabase
from services.curriculum_generator import generate_curriculum

logger = logging.getLogger(__name__)
gen_bp = Blueprint("generate", __name__, url_prefix="/api")


@gen_bp.route("/generate-curriculum/<slug>", methods=["POST"])
def generate_curriculum_api(slug):
    """Generate a 30-day curriculum for a topic and save to database.
    Called from the topic detail page when user clicks 'Generate My 30-Day Curriculum'."""
    
    if not g.user:
        return jsonify({"status": "error", "error": "Not logged in"}), 401
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    # Check if user is enrolled
    pipeline = sb.table("freelance_pipeline").select("id") \
        .eq("user_id", user_id).eq("topic", slug).limit(1).execute()
    if not pipeline.data:
        return jsonify({"status": "error", "error": "You must enroll first"}), 400
    
    # Get topic info
    from routes.topics import CURATED_TOPICS
    topic = next((t for t in CURATED_TOPICS if t["slug"] == slug), None)
    topic_name = topic["name"] if topic else slug.replace("-", " ").title()
    
    # Get topic DB record
    topic_db = sb.table("topics").select("id").eq("slug", slug).limit(1).execute()
    if not topic_db.data:
        return jsonify({"status": "error", "error": "Topic not found"}), 404
    
    topic_id = topic_db.data[0]["id"]
    
    # Check if curriculum already exists (don't duplicate)
    existing = sb.table("curricula").select("id").eq("topic_id", topic_id).limit(1).execute()
    if existing.data:
        day_count = sb.table("curriculum_days").select("id", count="exact") \
            .eq("curriculum_id", existing.data[0]["id"]).execute()
        if getattr(day_count, 'count', 0) or 0 >= 30:
            return jsonify({"status": "complete", "days": getattr(day_count, 'count', 0)})
        curr_id = existing.data[0]["id"]
    else:
        curr = sb.table("curricula").insert({
            "topic_id": topic_id, "total_days": 30
        }).execute()
        curr_id = curr.data[0]["id"]
    
    # Get user's linked platforms for platform-specific days
    linked_platforms = []
    try:
        plat = sb.table("user_platforms").select("platform") \
            .eq("user_id", user_id).eq("status", "verified").execute()
        linked_platforms = [p["platform"] for p in (plat.data or [])]
    except Exception:
        pass
    
    # Generate curriculum (will use LLM or fallback)
    try:
        curriculum = generate_curriculum(topic_name, 30, platforms=linked_platforms)
    except Exception as e:
        logger.error(f"Curriculum generation failed: {e}")
        return jsonify({"status": "error", "error": f"Generation failed: {e}"}), 500
    
    if not curriculum or len(curriculum) == 0:
        return jsonify({"status": "error", "error": "Generated 0 days"}), 500
    
    # Save days to database
    saved = 0
    for day in curriculum:
        try:
            sb.table("curriculum_days").insert({
                "curriculum_id": curr_id,
                "day_number": day.get("day_number", saved + 1),
                "title": day.get("title", f"Day {saved + 1}"),
                "description": day.get("description", ""),
                "learning_objectives": day.get("description", ""),
                "practice_task": day.get("practice_task", "Practice exercise"),
                "apply_task": day.get("apply_task", "Apply what you learned"),
                "video_title": day.get("video_title", f"{topic_name} — Day {saved + 1}"),
            }).execute()
            saved += 1
        except Exception as e:
            logger.warning(f"Failed to save day {day.get('day_number')}: {e}")
    
    logger.info(f"Saved {saved}/{len(curriculum)} curriculum days for {topic_name}")
    
    return jsonify({
        "status": "complete",
        "days": saved,
        "total": len(curriculum),
        "message": f"Generated {saved} days of curriculum"
    })
