"""
Progress routes — mark video watched, practice done, apply done
"""
from flask import Blueprint, request, jsonify, g
from services.supabase_client import get_supabase

progress_bp = Blueprint("progress", __name__, url_prefix="/api/progress")


@progress_bp.route("/mark", methods=["POST"])
def mark_progress():
    """Mark a section as complete for today's lesson."""
    if not g.user:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.get_json() or {}
    cohort_video_id = data.get("cohort_video_id")
    field = data.get("field")  # 'video_watched' | 'practice_completed' | 'apply_completed'
    
    if not cohort_video_id or field not in ("video_watched", "practice_completed", "apply_completed"):
        return jsonify({"error": "Invalid request"}), 400
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    # Check if progress record exists
    existing = sb.table("user_progress").select("*") \
        .eq("user_id", user_id) \
        .eq("cohort_video_id", cohort_video_id) \
        .limit(1) \
        .execute()
    
    if existing.data:
        sb.table("user_progress").update({
            field: True,
            "updated_at": "now()"
        }).eq("id", existing.data[0]["id"]).execute()
    else:
        sb.table("user_progress").insert({
            "user_id": user_id,
            "cohort_video_id": cohort_video_id,
            field: True,
        }).execute()
    
    # If all 3 are done, update freelance pipeline stage
    updated = sb.table("user_progress").select("*") \
        .eq("user_id", user_id) \
        .eq("cohort_video_id", cohort_video_id) \
        .limit(1) \
        .execute()
    
    if updated.data:
        p = updated.data[0]
        if p.get("video_watched") and p.get("practice_completed") and p.get("apply_completed"):
            # Advance to 'applying' stage if still in 'learning'
            sb.table("freelance_pipeline").update({
                "stage": "applying",
                "updated_at": "now()"
            }).eq("user_id", user_id).eq("stage", "learning").execute()
    
    return jsonify({"success": True})


@progress_bp.route("/rate", methods=["POST"])
def rate_day():
    """Rate today's lesson (1-5)."""
    if not g.user:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.get_json() or {}
    cohort_video_id = data.get("cohort_video_id")
    rating = data.get("rating")
    
    if not cohort_video_id or not (1 <= rating <= 5):
        return jsonify({"error": "Invalid request"}), 400
    
    sb = get_supabase()
    
    existing = sb.table("user_progress").select("id") \
        .eq("user_id", g.user["id"]) \
        .eq("cohort_video_id", cohort_video_id) \
        .limit(1) \
        .execute()
    
    if existing.data:
        sb.table("user_progress").update({
            "self_rating": rating,
            "updated_at": "now()"
        }).eq("id", existing.data[0]["id"]).execute()
    else:
        sb.table("user_progress").insert({
            "user_id": g.user["id"],
            "cohort_video_id": cohort_video_id,
            "self_rating": rating,
        }).execute()
    
    return jsonify({"success": True})
