"""
Generate Curriculum API — day-by-day generation with real-time progress.

Progress + per-day log lines are persisted to `curriculum_generation_log`
(DB-backed), so status polls work across gunicorn workers and the user can
always see what the background job is doing — via /api/generation-status/<slug>
or /api/generation-log/<slug>.
"""
import logging
import os
import threading
import json
from datetime import datetime, timezone
from flask import Blueprint, jsonify, g
from services.supabase_client import get_supabase
from services.curriculum_generator import generate_curriculum

logger = logging.getLogger(__name__)
gen_bp = Blueprint("generate", __name__, url_prefix="/api")

# In-memory progress tracker (fast path for the same worker; DB is source of truth)
_progress_tracker = {}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _log_entry(day, level, msg):
    """Structured log line for the generation log."""
    return {"ts": _now_iso(), "day": day, "level": level, "msg": msg}


def _update_genlog(slug, topic_id, **fields):
    """Upsert the DB-backed generation log row.

    If the curriculum_generation_log table doesn't exist yet (PGRST205),
    fall back to video_production_log (schema-migrated table that accepts
    inserts) so async logs work immediately; upgrade to the dedicated table
    once schema.sql DDL is applied.
    """
    try:
        sb = get_supabase()
        row = sb.table("curriculum_generation_log").select("id,log_entries") \
            .eq("topic_slug", slug).order("updated_at", desc=True).limit(1).execute()
        if row.data:
            rid = row.data[0]["id"]
            entries = row.data[0].get("log_entries") or []
            if fields.get("append_entry"):
                entries = (entries or []) + [fields.pop("append_entry")]
            fields.setdefault("updated_at", _now_iso())
            fields["log_entries"] = entries
            sb.table("curriculum_generation_log").update(fields).eq("id", rid).execute()
        else:
            append = fields.pop("append_entry", None)
            fields.setdefault("updated_at", _now_iso())
            fields["log_entries"] = [append] if append else (fields.get("log_entries") or [])
            sb.table("curriculum_generation_log").insert({
                "topic_id": topic_id, "topic_slug": slug, **fields
            }).execute()
    except Exception as e:
        msg = str(e)
        if "PGRST205" in msg or "Could not find the table" in msg:
            logger.warning(
                "curriculum_generation_log missing — falling back to video_production_log "
                "for async logs. Run schema.sql to enable the dedicated table.")
            _update_vplog_fallback(slug, topic_id, **fields)
        else:
            logger.error(f"genlog update failed: {e}")


def _update_vplog_fallback(slug, topic_id, **fields):
    """Fallback async-log sink using the schema-migrated video_production_log table.

    Each update creates one row (step='curriculum:<slug>'); log_entries JSON is
    stored in output_path so /api/generation-log can reconstruct it.
    """
    try:
        sb = get_supabase()
        append = fields.pop("append_entry", None)
        # Read the most recent row's accumulated entries
        prev = None
        try:
            rows = sb.table("video_production_log").select("output_path,status") \
                .eq("step", f"curriculum:{slug}") \
                .order("started_at", desc=True).limit(1).execute()
            if rows.data:
                prev = rows.data[0]
        except Exception:
            pass
        entries = []
        if prev and prev.get("output_path"):
            try:
                entries = json.loads(prev["output_path"])
            except Exception:
                entries = []
        if append:
            entries = (entries or []) + [append]
        status = fields.get("status", "running")
        # Terminal rows: update the latest row; otherwise insert a new one
        if prev and status in ("complete", "error"):
            sb.table("video_production_log").update({
                "status": status,
                "completed_at": _now_iso(),
                "error_message": fields.get("message", "")[:2000],
                "output_path": json.dumps(entries[-200:]),
            }).eq("step", f"curriculum:{slug}") \
              .order("started_at", desc=True).limit(1).execute()
        else:
            sb.table("video_production_log").insert({
                "step": f"curriculum:{slug}",
                "status": status,
                "started_at": _now_iso(),
                "error_message": fields.get("message", "")[:2000],
                "output_path": json.dumps(entries[-200:]),
            }).execute()
    except Exception as e:
        logger.error(f"vplog fallback write failed: {e}")


def _get_llm_config():
    """Get LLM API configuration — tries multiple providers in order."""
    # Priority 1: Environment variables (set on Render)
    api_url = os.environ.get("LLM_API_URL", "")
    api_key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "")

    # Priority 2: OpenRouter from vision-tool config
    if not api_key:
        try:
            import json as _json
            with open(os.path.expanduser("~/Documents/vision-tool/config.json")) as f:
                vc = _json.load(f)
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


@gen_bp.route("/regenerate-day/<slug>/<int:day_number>", methods=["POST"])
def regenerate_single_day(slug, day_number):
    """Regenerate a single day's lesson if it has fallback/generic content.
    Only works when the LLM is available — returns error otherwise."""
    if not g.user:
        return jsonify({"status": "error", "error": "Not logged in"}), 401

    sb = get_supabase()
    user_id = g.user["id"]

    # Verify user has access to this topic
    profile = sb.table("user_profiles").select("cohort_id").eq("user_id", user_id).limit(1).execute()
    cohort_id = profile.data[0]["cohort_id"] if profile.data else None
    if not cohort_id:
        return jsonify({"status": "error", "error": "Not enrolled"}), 403

    # Get the topic's curriculum
    topic_resp = sb.table("topics").select("id,name").eq("slug", slug).limit(1).execute()
    if not topic_resp.data:
        return jsonify({"status": "error", "error": "Topic not found"}), 404
    topic = topic_resp.data[0]

    cur_resp = sb.table("curricula").select("id").eq("topic_id", topic["id"]).limit(1).execute()
    if not cur_resp.data:
        return jsonify({"status": "error", "error": "No curriculum"}), 404
    curr_id = cur_resp.data[0]["id"]

    # Check if current content is fallback
    day_resp = sb.table("curriculum_days").select("*") \
        .eq("curriculum_id", curr_id).eq("day_number", day_number).limit(1).execute()
    if not day_resp.data:
        return jsonify({"status": "error", "error": "Day not found"}), 404

    current = day_resp.data[0]
    from services.curriculum_generator import is_fallback_content
    if not is_fallback_content(current):
        return jsonify({"status": "ok", "message": "Content is already good quality"})

    # Check LLM availability
    api_url, api_key, model = _get_llm_config()
    if not api_url or not api_key:
        return jsonify({"status": "error", "error": "LLM not available — cannot regenerate"}), 503

    # Regenerate this single day
    try:
        from app import create_app
        app = create_app()
        with app.app_context():
            import flask
            flask.current_app.config["LLM_API_URL"] = api_url
            flask.current_app.config["LLM_API_KEY"] = api_key
            flask.current_app.config["LLM_MODEL"] = model
            flask.current_app.config["LLM_TIMEOUT"] = 20

            day = _generate_one_day(day_number, topic["name"], [])
            if not day or is_fallback_content(day):
                return jsonify({"status": "error", "error": "Could not generate quality content — LLM may be overloaded"}), 500

            # Update the existing row
            hook = day.get("hook", "")
            concept = day.get("concept", day.get("description", ""))
            practice = day.get("practice", day.get("practice_task", ""))
            retrieval = day.get("retrieval", "")
            spaced = day.get("spaced_review", "")
            preview_text = day.get("preview", "")

            sb.table("curriculum_days").update({
                "title": day.get("title", current["title"]),
                "description": f"{hook}\n\n{concept}"[:2000] if hook else concept[:2000],
                "learning_objectives": hook[:500],
                "practice_task": f"{practice}\n\n## Retrieval\n{retrieval}"[:2000] if retrieval else practice[:2000],
                "apply_task": f"{spaced}\n\n{preview_text}"[:1000] if spaced else preview_text[:1000],
                "video_title": day.get("video_title", current.get("video_title", "")),
            }).eq("id", current["id"]).execute()

            return jsonify({"status": "ok", "message": f"Day {day_number} regenerated successfully"})
    except Exception as e:
        logger.error(f"Regenerate day {day_number} failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@gen_bp.route("/generate-curriculum/<slug>", methods=["POST"])
def generate_curriculum_api(slug):
    """Generate curriculum day-by-day. Frontend polls /status for progress."""
    if not g.user:
        return jsonify({"status": "error", "error": "Not logged in"}), 401

    sb = get_supabase()
    user_id = g.user["id"]

    # Verify enrollment — either pipeline record OR cohort assignment for this topic
    pipeline = sb.table("freelance_pipeline").select("id") \
        .eq("user_id", user_id).eq("topic", slug).limit(1).execute()

    is_enrolled = bool(pipeline.data)
    if not is_enrolled:
        # Check if user's cohort is for this topic
        try:
            prof = sb.table("user_profiles").select("cohort_id").eq("user_id", user_id).limit(1).execute()
            cohort_id = prof.data[0].get("cohort_id") if prof.data else None
            if cohort_id:
                topic_db = sb.table("topics").select("id").eq("slug", slug).limit(1).execute()
                if topic_db.data:
                    cohort = sb.table("cohorts").select("topic_id").eq("id", cohort_id).limit(1).execute()
                    if cohort.data and cohort.data[0].get("topic_id") == topic_db.data[0]["id"]:
                        is_enrolled = True
        except Exception:
            pass

    if not is_enrolled:
        return jsonify({"status": "error", "error": "You must enroll first"}), 400

    # Get topic info
    from routes.topics import CURATED_TOPICS
    topic = next((t for t in CURATED_TOPICS if t["slug"] == slug), None)
    topic_name = topic["name"] if topic else slug.replace("-", " ").title()

    topic_db = sb.table("topics").select("id").eq("slug", slug).limit(1).execute()
    if not topic_db.data:
        return jsonify({"status": "error", "error": "Topic not found"}), 404

    topic_id = topic_db.data[0]["id"]

    # Guard: if a generation is already running for this slug (in-memory or
    # DB-backed), don't start a second thread — return the running state.
    mem = _progress_tracker.get(slug)
    if mem and mem.get("status") == "generating":
        return jsonify({"status": "generating", "message": "Generation already in progress",
                        "current_day": mem.get("current_day", 0), "total_days": 30})
    try:
        row = sb.table("curriculum_generation_log").select("status").eq("topic_slug", slug) \
            .order("updated_at", desc=True).limit(1).execute()
        if row.data and row.data[0].get("status") == "running":
            return jsonify({"status": "generating", "message": "Generation already in progress"})
    except Exception:
        pass

    # Get or create curriculum record
    curr_resp = sb.table("curricula").select("id").eq("topic_id", topic_id).limit(1).execute()
    if curr_resp.data:
        curr_id = curr_resp.data[0]["id"]
        existing = sb.table("curriculum_days").select("id", count="exact") \
            .eq("curriculum_id", curr_id).execute()
        if (getattr(existing, 'count', 0) or 0) >= 30:
            # Backfill cohort_videos if missing, then report complete
            _backfill_cohort_videos(sb, slug, user_id, curr_id)
            # Record the completion in the async log so status/log endpoints
            # reflect reality even when generation happened earlier
            _progress_tracker[slug] = {
                "status": "complete", "current_day": 30, "total_days": 30,
                "percent": 100, "last_title": "Complete!", "topic": topic_name,
            }
            _update_genlog(slug, topic_id, status="complete", current_day=30,
                           total_days=30, percent=100, last_title="Complete!",
                           message=f"Curriculum already exists ({existing.count} days)",
                           append_entry=_log_entry(30, "info",
                                                   f"Curriculum already complete ({existing.count} days)"))
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

    # Initialize progress (DB-backed so all workers see it)
    _progress_tracker[slug] = {
        "status": "generating",
        "current_day": 0,
        "total_days": 30,
        "topic": topic_name,
        "percent": 0,
        "last_title": "Starting...",
    }
    _update_genlog(slug, topic_id, status="running", current_day=0, total_days=30,
                   percent=0, last_title="Starting...", message="Generation started",
                   append_entry=_log_entry(0, "info", f"Generation started for {topic_name}"))

    # Start background generation
    thread = threading.Thread(
        target=_generate_in_background,
        args=(slug, curr_id, topic_id, topic_name, 30, linked_platforms, user_id),
        daemon=True
    )
    thread.start()

    return jsonify({
        "status": "started",
        "message": f"Generating 30-day curriculum for {topic_name}"
    })


def _backfill_cohort_videos(sb, slug, user_id, curr_id):
    """Ensure cohort_videos rows exist for every curriculum day (fixes day links)."""
    try:
        prof = sb.table("user_profiles").select("cohort_id").eq("user_id", user_id).limit(1).execute()
        cohort_id = prof.data[0].get("cohort_id") if prof.data else None
        if not cohort_id:
            return
        days = sb.table("curriculum_days").select("id,day_number") \
            .eq("curriculum_id", curr_id).order("day_number").execute()
        for d in (days.data or []):
            existing = sb.table("cohort_videos").select("id") \
                .eq("cohort_id", cohort_id).eq("day_number", d["day_number"]).limit(1).execute()
            if not existing.data:
                sb.table("cohort_videos").insert({
                    "cohort_id": cohort_id,
                    "day_number": d["day_number"],
                    "curriculum_day_id": d["id"],
                    "youtube_title": f"Day {d['day_number']}",
                    "production_status": "ready",
                }).execute()
        logger.info(f"Backfilled {len(days.data or [])} cohort_videos for {slug}")
    except Exception as e:
        logger.warning(f"cohort_videos backfill failed: {e}")


@gen_bp.route("/generation-status/<slug>")
def generation_status(slug):
    """Poll this endpoint to get real-time generation progress (DB-backed)."""
    # 1) Fast path: in-memory (same worker)
    mem = _progress_tracker.get(slug)
    if mem and mem.get("status") in ("generating", "complete", "error"):
        return jsonify(mem)
    # 2) DB fallback (cross-worker)
    try:
        sb = get_supabase()
        row = sb.table("curriculum_generation_log").select(
            "status,current_day,total_days,percent,last_title,message,updated_at"
        ).eq("topic_slug", slug).order("updated_at", desc=True).limit(1).execute()
        if row.data:
            r = row.data[0]
            # Re-hydrate in-memory cache
            _progress_tracker[slug] = r
            return jsonify(r)
    except Exception as e:
        logger.error(f"status DB lookup failed: {e}")
    return jsonify({"status": "unknown", "current_day": 0, "total_days": 30, "percent": 0})


@gen_bp.route("/generation-log/<slug>")
def generation_log(slug):
    """Structured log of the background generation job — what's happening in bg."""
    try:
        sb = get_supabase()
        row = sb.table("curriculum_generation_log").select(
            "status,current_day,total_days,percent,last_title,message,log_entries,updated_at"
        ).eq("topic_slug", slug).order("updated_at", desc=True).limit(1).execute()
        if row.data:
            return jsonify(row.data[0])
    except Exception as e:
        logger.error(f"genlog fetch failed: {e}")
    # Fallback: read from video_production_log (schema-migrated sink)
    try:
        sb = get_supabase()
        rows = sb.table("video_production_log").select("status,error_message,output_path,started_at") \
            .eq("step", f"curriculum:{slug}").order("started_at", desc=True).limit(1).execute()
        if rows.data:
            r = rows.data[0]
            entries = []
            if r.get("output_path"):
                try:
                    entries = json.loads(r["output_path"])
                except Exception:
                    entries = []
            return jsonify({
                "status": r.get("status", "unknown"),
                "message": r.get("error_message", ""),
                "log_entries": entries,
                "percent": 100 if r.get("status") == "complete" else 0,
                "current_day": len(entries),
                "total_days": 30,
            })
    except Exception as e:
        logger.error(f"vplog fetch failed: {e}")
    # Last resort: surface whatever the in-memory tracker knows
    mem = _progress_tracker.get(slug)
    if mem:
        return jsonify({"status": mem.get("status", "unknown"),
                        "message": mem.get("message", mem.get("last_title", "")),
                        "log_entries": [], "percent": mem.get("percent", 0),
                        "current_day": mem.get("current_day", 0),
                        "total_days": mem.get("total_days", 30)})
    return jsonify({"status": "unknown", "log_entries": [], "message": "No generation log yet"})


def _generate_in_background(slug, curr_id, topic_id, topic_name, total_days, linked_platforms, user_id):
    """Generate curriculum day-by-day, saving each day with live progress + logs."""
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
            flask.current_app.config["LLM_TIMEOUT"] = 20

            sb = get_supabase()

            # Get the user's cohort
            cohort_id = None
            try:
                user_profile = sb.table("user_profiles").select("cohort_id").eq("user_id", user_id).limit(1).execute()
                cohort_id = user_profile.data[0]["cohort_id"] if user_profile.data else None
            except Exception:
                pass

            # Generate + save day by day (progress updates live)
            saved = 0
            for day_num in range(1, total_days + 1):
                day = None
                try:
                    day = _generate_one_day(day_num, topic_name, linked_platforms)
                    if not day:
                        logger.warning(f"[gen:{slug}] day {day_num}: no lesson returned, skipping")
                        _update_genlog(slug, topic_id,
                                       append_entry=_log_entry(day_num, "warn",
                                                               "No lesson returned — skipped"))
                        continue

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

                    # ── Quality Gate: reject fallback/generic content ──
                    from services.curriculum_generator import is_fallback_content
                    if is_fallback_content(day):
                        _update_genlog(slug, topic_id,
                                       append_entry=_log_entry(day_num, "warn",
                                                               f"Day {day_num} REJECTED — fallback content detected, will retry"))
                        # Retry once with LLM (fallback is only when LLM failed)
                        day = _generate_one_day(day_num, topic_name, linked_platforms)
                        if day and not is_fallback_content(day):
                            # Re-pack the retried content
                            hook = day.get("hook", "")
                            concept = day.get("concept", day.get("description", ""))
                            practice = day.get("practice", day.get("practice_task", ""))
                            retrieval = day.get("retrieval", "")
                            spaced = day.get("spaced_review", "")
                            preview_text = day.get("preview", "")
                            full_description = f"{hook}\n\n{concept}" if hook else concept
                            full_practice = f"{practice}\n\n## Retrieval\n{retrieval}" if retrieval else practice
                            full_apply = f"{spaced}\n\n{preview_text}" if spaced else preview_text
                            _update_genlog(slug, topic_id,
                                           append_entry=_log_entry(day_num, "info",
                                                                   f"Day {day_num} retry succeeded"))
                        else:
                            # Still fallback after retry — skip this day entirely
                            _update_genlog(slug, topic_id,
                                           append_entry=_log_entry(day_num, "error",
                                                                   f"Day {day_num} SKIPPED — could not generate quality content"))
                            continue

                    day_data = {
                        "curriculum_id": curr_id,
                        "day_number": day_num,
                        "title": day.get("title", f"Day {day_num}"),
                        "description": full_description[:2000],
                        "learning_objectives": hook[:500],
                        "practice_task": full_practice[:2000],
                        "apply_task": full_apply[:1000],
                        "video_title": day.get("video_title", f"{topic_name} — Day {day_num}"),
                    }
                    sb.table("curriculum_days").insert(day_data).execute()
                    saved += 1

                    # Create cohort_video so day links work
                    if cohort_id:
                        try:
                            existing_video = sb.table("cohort_videos").select("id") \
                                .eq("cohort_id", cohort_id).eq("day_number", day_num).limit(1).execute()
                            if not existing_video.data:
                                # find the inserted curriculum_day id
                                cd = sb.table("curriculum_days").select("id") \
                                    .eq("curriculum_id", curr_id).eq("day_number", day_num).limit(1).execute()
                                sb.table("cohort_videos").insert({
                                    "cohort_id": cohort_id,
                                    "day_number": day_num,
                                    "curriculum_day_id": cd.data[0]["id"] if cd.data else None,
                                    "youtube_title": day.get("video_title", f"{topic_name} — Day {day_num}"),
                                    "production_status": "ready",
                                }).execute()
                        except Exception as e:
                            logger.warning(f"[gen:{slug}] cohort_video day {day_num} failed: {e}")

                    _update_genlog(slug, topic_id,
                                   append_entry=_log_entry(day_num, "info",
                                                           f"Day {day_num} saved: {day.get('title', '')[:60]}"))
                except Exception as e:
                    logger.warning(f"[gen:{slug}] day {day_num} failed: {e}")
                    _update_genlog(slug, topic_id,
                                   append_entry=_log_entry(day_num, "error", f"Day {day_num} failed: {e}"))

                # Update progress after each day (generation + save)
                pct = round(day_num / total_days * 100)
                prog = {
                    "status": "generating",
                    "current_day": day_num,
                    "total_days": total_days,
                    "percent": pct,
                    "last_title": day.get("title", f"Day {day_num}") if day else f"Day {day_num}",
                    "topic": topic_name,
                }
                _progress_tracker[slug] = prog
                _update_genlog(slug, topic_id, status="running", current_day=day_num,
                               total_days=total_days, percent=pct,
                               last_title=prog["last_title"],
                               message=f"Generating day {day_num}/{total_days}")

            # ── Final Quality Gate: validate the saved curriculum ──
            from services.curriculum_generator import validate_curriculum
            all_saved = sb.table("curriculum_days") \
                .select("title,description,practice_task,apply_task") \
                .eq("curriculum_id", curr_id).order("day_number").execute().data or []
            qv = validate_curriculum(all_saved)
            if not qv["valid"]:
                logger.warning(f"[gen:{slug}] Quality gate FAILED: {qv['errors']}")
                _update_genlog(slug, topic_id,
                               append_entry=_log_entry(0, "error",
                                                       f"Quality gate: {'; '.join(qv['errors'])}"))

            # Mark complete
            final = {
                "status": "complete",
                "current_day": total_days,
                "total_days": total_days,
                "percent": 100,
                "last_title": "Complete!",
                "topic": topic_name,
                "quality_valid": qv["valid"],
                "quality_errors": qv["errors"],
            }
            _progress_tracker[slug] = final
            _update_genlog(slug, topic_id, status="complete", current_day=total_days,
                           total_days=total_days, percent=100, last_title="Complete!",
                           message=f"Saved {saved}/{total_days} days" + (f" (quality issues: {'; '.join(qv['errors'])})" if qv["errors"] else ""),
                           append_entry=_log_entry(total_days, "info",
                                                   f"Generation complete: {saved}/{total_days} days saved" +
                                                   (f" ⚠ Quality: {'; '.join(qv['errors'])}" if qv["errors"] else " ✓ Quality passed")))

            logger.info(f"[gen:{slug}] saved {saved}/{total_days} days for {topic_name}")

    except Exception as e:
        logger.error(f"[gen:{slug}] background generation failed: {e}")
        _progress_tracker[slug] = {"status": "error", "error": str(e)}
        try:
            _update_genlog(slug, topic_id, status="error", message=f"Generation failed: {e}",
                           append_entry=_log_entry(0, "error", f"Generation failed: {e}"))
        except Exception:
            pass


def _generate_one_day(day_num, topic_name, linked_platforms):
    """Generate a single day's lesson (LLM or fallback)."""
    from services.curriculum_generator import _generate_daily_lesson, _fallback_lesson, _get_day_focus, _get_learning_objective
    try:
        # Determine week/theme
        weekly_themes = [
            (1, "Foundation", "Core concepts and first tangible output"),
            (2, "Building", "Intermediate skills with real examples"),
            (3, "Application", "Portfolio work and client proposals"),
            (4, "Mastery", "Income generation and business skills"),
        ]
        week_num = min(4, (day_num - 1) // 7 + 1)
        week_theme, week_focus = weekly_themes[week_num - 1][1], weekly_themes[week_num - 1][2]

        focus = _get_day_focus(day_num, week_num, week_theme, topic_name)
        objective = _get_learning_objective(day_num, week_num, topic_name)

        lesson = _generate_daily_lesson(day_num, week_num, week_theme, focus, objective, topic_name)
        if lesson:
            return lesson
    except Exception:
        pass
    return _fallback_lesson(day_num, topic_name)
