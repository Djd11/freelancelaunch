"""
Dynamic Topic Enrollment — create curriculum from search results
"""
import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, g
from services.supabase_client import get_supabase
from services.curriculum_generator import generate_curriculum

logger = logging.getLogger(__name__)
enroll_bp = Blueprint("enroll_dynamic", __name__, url_prefix="/enroll")


@enroll_bp.route("/new", methods=["POST"])
def enroll_new_topic():
    """User searched for a topic, now wants to create a 30-day curriculum and enroll."""
    if not g.user:
        return jsonify({"error": "Not logged in", "redirect": url_for("auth.login")}), 401
    
    data = request.get_json() or {}
    topic_name = data.get("topic", "").strip()
    topic_slug = topic_name.lower().replace(" ", "-").replace("/", "-")[:40]
    
    if not topic_name or len(topic_name) < 3:
        return jsonify({"error": "Topic name must be at least 3 characters"}), 400
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    # 1. Check if topic already exists in our curated list
    from routes.topics import CURATED_TOPICS
    existing_topic = next((t for t in CURATED_TOPICS if topic_slug in t["slug"]), None)
    
    topic_id = topic_slug
    
    if existing_topic:
        topic_id = existing_topic["slug"]
    else:
        # 2. Create a new topic record in DB
        try:
            sb.table("topics").upsert({
                "slug": topic_slug,
                "name": topic_name,
                "description": f"A 30-day curriculum for {topic_name}",
                "demand_score": 70,
                "job_count": 100,
                "avg_rate": 30,
                "is_curated": False,
            }, on_conflict="slug").execute()
        except Exception as e:
            logger.warning(f"Topic insert failed (may already exist): {e}")
    
    # 3. Generate curriculum using LLM
    try:
        # Get user's linked platforms to customize the curriculum
        linked_platforms = []
        try:
            plat_resp = sb.table("user_platforms").select("platform") \
                .eq("user_id", user_id).eq("status", "verified").execute()
            linked_platforms = [p["platform"] for p in (plat_resp.data or [])]
        except Exception:
            pass
        
        curriculum = generate_curriculum(topic_name, 30, platforms=linked_platforms)
    except Exception as e:
        logger.warning(f"LLM curriculum generation failed, using fallback: {e}")
        curriculum = None
    
    # 4. Create or find cohort
    from datetime import date, timedelta
    today = date.today()
    
    cohort_resp = sb.table("cohorts").select("*") \
        .eq("topic_id", topic_id) \
        .in_("status", ["upcoming", "active"]) \
        .order("start_date", desc=True).limit(1).execute()
    
    if cohort_resp.data:
        cohort = cohort_resp.data[0]
        cohort_id = cohort["id"]
    else:
        # Determine next start date
        if today.day < 15:
            start_date = date(today.year, today.month, 1)
            if start_date <= today:
                start_date = date(today.year + 1, 1, 1) if today.month == 12 else date(today.year, today.month + 1, 1)
        else:
            start_date = date(today.year, today.month, 15)
            if start_date <= today:
                start_date = date(today.year + 1, 1, 1) if today.month == 12 else date(today.year + 1, 1, 1)
        
        cohort_resp = sb.table("cohorts").insert({
            "topic_id": topic_id,
            "name": f"{topic_name} — {start_date.strftime('%B %Y')}",
            "start_date": start_date.isoformat(),
            "end_date": (start_date + timedelta(days=30)).isoformat(),
            "max_days": 30,
            "status": "upcoming",
        }).execute()
        cohort = cohort_resp.data[0]
        cohort_id = cohort["id"]
    
    # 5. If curriculum was generated, save curriculum days
    if curriculum and len(curriculum) > 0:
        # Check if curriculum already exists
        curr_resp = sb.table("curricula").select("id").eq("topic_id", topic_id).limit(1).execute()
        if not curr_resp.data:
            curr = sb.table("curricula").insert({
                "topic_id": topic_id,
                "total_days": len(curriculum),
            }).execute()
            curr_id = curr.data[0]["id"]
            
            for day in curriculum:
                try:
                    sb.table("curriculum_days").insert({
                        "curriculum_id": curr_id,
                        "day_number": day.get("day_number", 1),
                        "title": day.get("title", f"Day {day.get('day_number', 1)}"),
                        "description": day.get("description", ""),
                        "practice_task": day.get("practice_task", ""),
                        "apply_task": day.get("apply_task", ""),
                        "video_title": day.get("video_title", f"{topic_name} — Day {day.get('day_number', 1)}"),
                    }).execute()
                except Exception as e:
                    logger.warning(f"Day insert failed: {e}")
    
    # 6. Update user profile
    sb.table("user_profiles").update({
        "cohort_id": cohort_id,
        "selected_topic_id": topic_id,
    }).eq("user_id", user_id).execute()
    
    # 7. Create pipeline
    existing = sb.table("freelance_pipeline").select("id").eq("user_id", user_id).eq("topic", topic_id).limit(1).execute()
    if not existing.data:
        sb.table("freelance_pipeline").insert({
            "user_id": user_id,
            "topic": topic_id,
            "stage": "exploring",
        }).execute()
    
    flash(f"🎉 30-day curriculum created for {topic_name}! Now link your freelance platforms.", "success")
    return jsonify({
        "status": "enrolled",
        "topic": topic_name,
        "redirect": url_for("platforms.setup"),
    })
