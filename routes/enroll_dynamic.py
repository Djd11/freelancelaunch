"""
Dynamic Topic Enrollment — create curriculum from search results
"""
import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, g
from services.supabase_client import get_supabase

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
    
    if existing_topic:
        # Ensure the topics row exists so we can link by UUID
        try:
            sb.table("topics").upsert({
                "slug": existing_topic["slug"],
                "name": existing_topic["name"],
                "description": existing_topic.get("description", ""),
                "demand_score": existing_topic.get("demand_score", 70),
                "job_count": existing_topic.get("job_count", 100),
                "avg_rate": existing_topic.get("avg_rate", 30),
                "is_curated": True,
            }, on_conflict="slug").execute()
        except Exception as e:
            logger.warning(f"Curated topic upsert failed: {e}")
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
    
    # Resolve slug → topics.id UUID. cohorts.topic_id and
    # user_profiles.selected_topic_id are UUID FK columns — slug strings 500.
    lookup_slug = existing_topic["slug"] if existing_topic else topic_slug
    topic_id = lookup_slug
    try:
        tdb = sb.table("topics").select("id").eq("slug", lookup_slug).limit(1).execute()
        if tdb.data:
            topic_id = tdb.data[0]["id"]
    except Exception as e:
        logger.warning(f"Topic UUID lookup failed, falling back to slug: {e}")
    
    # 3. Curriculum generation is DEFERRED to the async background job
    # (POST /api/generate-curriculum/<slug>), which the day page triggers with
    # a live step-wise progress log. Synchronous generation here would block
    # the request and hide the async visibility the UX promises.
    linked_platforms = []
    try:
        plat_resp = sb.table("user_platforms").select("platform") \
            .eq("user_id", user_id).eq("status", "verified").execute()
        linked_platforms = [p["platform"] for p in (plat_resp.data or [])]
    except Exception:
        pass
    
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
    
    # 5. Kick off ASYNC curriculum generation in a background thread.
    # The day page (and /api/generation-log/<slug>) shows step-wise progress.
    try:
        import threading
        from routes.generate_api import _generate_in_background, _update_genlog, _log_entry
        # Ensure a curriculum row exists so the background job can save days
        curr_resp = sb.table("curricula").select("id").eq("topic_id", topic_id).limit(1).execute()
        if curr_resp.data:
            curr_id = curr_resp.data[0]["id"]
        else:
            curr = sb.table("curricula").insert({
                "topic_id": topic_id, "total_days": 30,
            }).execute()
            curr_id = curr.data[0]["id"]
        _update_genlog(topic_slug, topic_id, status="running", current_day=0,
                       total_days=30, percent=0, last_title="Starting...",
                       message=f"Generation started for {topic_name}",
                       append_entry=_log_entry(0, "info", f"Enrolled — starting async generation for {topic_name}"))
        t = threading.Thread(
            target=_generate_in_background,
            args=(topic_slug, curr_id, topic_id, topic_name, 30, linked_platforms, user_id),
            daemon=True
        )
        t.start()
        logger.info(f"Async generation started for {topic_name} ({topic_slug})")
    except Exception as e:
        logger.warning(f"Async generation kickoff failed: {e}")
    
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
