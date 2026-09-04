"""sprints blueprint — dashboard, day view, day completion, verification, badge (arch §4.2)."""
import datetime

from flask import Blueprint, render_template, request, redirect, url_for, g, jsonify, flash

from routes import (require_login, load_cluster, load_sprint, load_cohort,
                    load_meter, load_momentum, load_day, load_project, phase_a_done_days,
                    DAY_TO_PROJECT)
from services.verification_service import gate_a_passed, gate_b_passed, record as record_review
from services.verification_service import auto_check_gate_a, is_valid_url
from services.unlock_engine import recompute
from services.badge_engine import issue as issue_badge
from services.nudge_engine import nudge as nudge_for, recompute_confidence
from services.lesson_engine import content_day_cards
from . import obtain_supabase

sprints_bp = Blueprint("sprints", __name__)


def _try_resume_generation(sprint_id):
    """Lazily resume a sprint whose content is unfinished but not failed.

    After a server restart the in-memory ``_active_generations`` set is empty,
    so a partially-generated sprint looks like it lost content ("partial" /
    endless "generating" notice). The durable signal lives in the DB:
    ``should_resume_generation`` (active sprint + at least one empty day + no
    generation_error). When that holds, spawn the same background worker the
    enrollment/retry paths use and mark the sprint generating, so the UI
    auto-resumes instead of showing the error-ish "partial" state.

    Returns True when a resume thread was spawned, False otherwise. Never
    raises — a resume failure must not 500 the page.
    """
    from services.lesson_engine import (
        is_generating, should_resume_generation, start_generation,
    )
    if is_generating(sprint_id):
        return False
    try:
        sb = obtain_supabase()
        if not should_resume_generation(sb, sprint_id):
            return False
    except Exception:
        return False
    try:
        import threading
        from flask import current_app
        from routes.main import _generate_in_background
        start_generation(sprint_id)  # mark generating before the thread wakes
        app = current_app._get_current_object()
        threading.Thread(
            target=_generate_in_background, args=(app, sprint_id), daemon=True,
        ).start()
        return True
    except Exception:
        return False


@sprints_bp.route("/sprints/<sprint_id>")
def dashboard(sprint_id):
    gate = require_login()
    if gate:
        return gate
    sb = obtain_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint:
        return redirect(url_for("main.dashboard"))
    if sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("main.dashboard"))

    cluster = load_cluster(sb, sprint["cluster_key"]) or {"display_name": "Sprint", "cluster_key": sprint["cluster_key"], "icon": "⚡", "job_count": 0, "avg_rate": 0}
    cohort = load_cohort(sb, sprint.get("cohort_id"))
    meter = load_meter(sb, sprint_id)
    momentum = load_momentum(sb, g.user["id"])
    today = load_day(sb, sprint_id, sprint["current_day"]) or {"day_no": sprint["current_day"], "phase": sprint["phase"], "action_type": "copywork", "action_payload": {}}
    phase_a_days = phase_a_done_days(sb, sprint_id)
    # Per-day done status so the dashboard can render clickable day tracks.
    all_days = sb.table("sprint_days").select("day_no,title,is_done,action_type,action_payload") \
        .eq("sprint_id", sprint_id).order("day_no").execute().data
    day_done_map = {d["day_no"]: bool(d.get("is_done")) for d in all_days}
    content_days = content_day_cards(all_days)
    nudge = nudge_for(sprint, momentum)
    contracts = sb.table("contracts").select("*").eq("sprint_id", sprint_id).execute().data

    # Today-card check-items: Watch lesson ← today's lesson_watched (eng-spec J4);
    # Replicate ← today's copy-work project.done; Self-check ← all rubric items user-checked for all projects.
    today_payload = today.get("action_payload") or {}
    today_project_index = today_payload.get("project_index") or DAY_TO_PROJECT.get(today.get("day_no"))
    today_project = load_project(sb, sprint_id, today_project_index)
    gate_a = gate_a_passed(sb, sprint_id)

    # The stored phase advances by day count, so a learner who marked days done
    # without passing Gate A would see "SHIFT B · DAY 06" while the contract is
    # still locked — a label that runs ahead of reality (dogfood MINOR). Correct
    # the DISPLAYED phase to the highest gate actually passed; the stored value
    # and day counter are untouched.
    _gate_b = gate_b_passed(sb, sprint_id)
    disp_phase = "C" if _gate_b else ("B" if gate_a else "A")
    if sprint.get("phase") != disp_phase:
        sprint = {**sprint, "phase": disp_phase}

    # Check if all rubric items for all 3 projects are user-checked
    projects = sb.table("copywork_projects").select("rubric_checked, done") \
        .eq("sprint_id", sprint_id).order("project_index").execute().data
    all_rubric_checked = True
    for p in projects:
        if not p.get("done"):
            all_rubric_checked = False
            break
        rubric_checked = p.get("rubric_checked") or [False, False, False]
        if not all(rubric_checked):
            all_rubric_checked = False
            break

    # Live job feed: recent jobs from RSS/Freelancer for this cluster.
    live_jobs = sb.table("job_feed").select("title,source_url,skills,rate,source_platform,posted_at") \
        .eq("cluster_key", sprint["cluster_key"]).eq("status", "active") \
        .order("posted_at", desc=True).limit(10).execute().data
    # Update cluster job_count to reflect actual feed size.
    live_count = sb.table("job_feed").select("id", count="exact") \
        .eq("cluster_key", sprint["cluster_key"]).eq("status", "active").execute().count or 0
    cluster["live_job_count"] = live_count
    # RSS-sourced count for the badge.
    rss_count = sb.table("job_feed").select("id", count="exact") \
        .eq("cluster_key", sprint["cluster_key"]).eq("source_platform", "rss") \
        .eq("status", "active").execute().count or 0
    cluster["rss_job_count"] = rss_count

    return render_template(
        "sprint_dashboard.html",
        sprint=sprint, cluster=cluster, cohort=cohort, meter=meter,
        momentum=momentum, today=today, phase_a_days=phase_a_days,
        gate_a_pass=gate_a, gate_b_pass=_gate_b,
        today_lesson_watched=bool(today.get("lesson_watched")),
        today_project_done=bool(today_project and today_project.get("done")),
        today_rubric_checked=all_rubric_checked,
        nudge=nudge, contracts=contracts, day_done_map=day_done_map,
        live_jobs=live_jobs, content_days=content_days,
    )


@sprints_bp.route("/sprints/<sprint_id>/day/<int:day_no>")
def day(sprint_id, day_no):
    gate = require_login()
    if gate:
        return gate
    sb = obtain_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint:
        return redirect(url_for("main.dashboard"))
    if sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("main.dashboard"))

    day_row = load_day(sb, sprint_id, day_no)
    if not day_row:
        return redirect(url_for("sprints.dashboard", sprint_id=sprint_id))

    payload = day_row.get("action_payload") or {}
    project_index = payload.get("project_index") or DAY_TO_PROJECT.get(day_no)
    project = load_project(sb, sprint_id, project_index)
    meter = load_meter(sb, sprint_id)
    gap_fill_topic = project.get("gap_fill_topic") if project else None
    pct = int(round((meter["unlocked_count"] / meter["total_in_cluster"] * 100))) if meter.get("total_in_cluster") else 0

    # LLM-only content (async worker): render exactly what the worker wrote. If
    # this day's payload is still empty the page shows a "generating" notice;
    # if generation failed the worker stamped a visible generation_error.
    from services.lesson_engine import generation_error, clean_lesson
    lesson = clean_lesson(payload.get("lesson"))
    # Lazy resume after a restart: the in-memory active set is empty, so a
    # partially-generated sprint would otherwise show a dead "generating"
    # notice. The DB says content is unfinished but not failed — kick the
    # background worker so this empty day page auto-resumes. Never raises.
    if not lesson:
        _try_resume_generation(sprint_id)
    # Video props: real sprint progress for the player's punch-card outro
    # and day eyebrow (t4 blocker #3 — every video previously rendered
    # "Day 01" regardless of the actual day being viewed).
    days_done_rows = sb.table("sprint_days").select("day_no").eq(
        "sprint_id", sprint_id
    ).eq("is_done", True).execute().data
    days_done = len(days_done_rows or [])
    # A day that ALREADY has content renders it — a failure elsewhere in the
    # sprint (generation_error is sprint-wide, stamped on the first empty day)
    # must not hide this day's valid lesson. Only days still waiting on the
    # worker surface the sprint-wide failure instead of endless "generating".
    gen_error = payload.get("generation_error")
    if not lesson and not gen_error:
        gen_error = generation_error(sb, sprint_id)
    clone_steps = (project or {}).get("clone_steps") or []
    rubric = (project or {}).get("rubric") or []
    submitted_url = (project or {}).get("submitted_url")
    project_submitted = bool(project and is_valid_url(submitted_url))
    # The generated reference build spec — what to replicate INSTEAD of an
    # external link (content-quality P0-2). Stored on the project row when the
    # reference_spec column is migrated, else on this day's action_payload.
    reference_spec = payload.get("reference_spec") \
        or ((project or {}).get("reference_spec") or "")

    return render_template(
        "day.html",
        sprint=sprint, day=day_row, project=project, meter=meter,
        day_done=bool(day_row.get("is_done")), gap_fill_topic=gap_fill_topic, pct=pct,
        lesson=lesson, gen_error=gen_error, clone_steps=clone_steps, rubric=rubric,
        reference_spec=reference_spec,
        lesson_watched=bool(day_row.get("lesson_watched")),
        project_done=bool(project and project.get("done")),
        gate_a_pass=gate_a_passed(sb, sprint_id),
        project_submitted=project_submitted,
        days_done=days_done,
    )


@sprints_bp.route("/sprints/<sprint_id>/day/<int:day_no>/watched", methods=["POST"])
def mark_watched(sprint_id, day_no):
    """Toggle sprint_days.lesson_watched — the day-view 'Mark lesson watched'
    check-item (eng-spec J4). Plain-form POST, redirect back to the day view."""
    gate = require_login()
    if gate:
        return gate
    sb = obtain_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("main.dashboard"))
    day_row = load_day(sb, sprint_id, day_no)
    if not day_row:
        return redirect(url_for("sprints.dashboard", sprint_id=sprint_id))
    new_state = not bool(day_row.get("lesson_watched"))
    sb.table("sprint_days").update({"lesson_watched": new_state}) \
        .eq("sprint_id", sprint_id).eq("day_no", day_no).execute()
    return redirect(url_for("sprints.day", sprint_id=sprint_id, day_no=day_no))


@sprints_bp.route("/sprints/<sprint_id>/generation")
def generation(sprint_id):
    """Content-generation progress — the populated lesson payload count IS the
    DB-backed log (arch §7). Polled by the dashboard spinner."""
    gate = require_login()
    if gate:
        return gate
    sb = obtain_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return jsonify({"error": "not found"}), 404
    from services.lesson_engine import generation_progress, generation_error, day_status_map, is_generating, should_resume_generation
    generated, total = generation_progress(sb, sprint_id)
    err = generation_error(sb, sprint_id)
    day_map = day_status_map(sb, sprint_id)
    failed_days = [d for d, s in day_map.items() if s == "error"]
    active = is_generating(sprint_id)

    if not active and should_resume_generation(sb, sprint_id):
        # After a restart the in-memory active set is empty, so a
        # partially-generated sprint would read as "partial" / content-lost.
        # The DB says content is unfinished but not failed — auto-resume the
        # background worker so the dashboard spinner + auto-poll path works.
        _try_resume_generation(sprint_id)
        active = True

    if generated >= total:
        # All days have content — nothing to show.
        return jsonify({
            "status": "ready",
            "generated": generated,
            "total": total,
            "day_status": day_map,
        })

    if active:
        # Background thread is actively generating — show spinner + auto-poll.
        return jsonify({
            "status": "generating",
            "error": err,
            "generated": generated,
            "total": total,
            "day_status": day_map,
            "failed_days": failed_days,
        })

    # Not actively generating and content is incomplete — show static status.
    if failed_days:
        return jsonify({
            "status": "partial",
            "error": err,
            "generated": generated,
            "total": total,
            "day_status": day_map,
            "failed_days": failed_days,
        })

    # Some content exists, some days pending, no thread running.
    return jsonify({
        "status": "partial",
        "error": err,
        "generated": generated,
        "total": total,
        "day_status": day_map,
        "failed_days": failed_days,
    })


@sprints_bp.route("/sprints/<sprint_id>/generation/retry", methods=["POST"])
def retry_generation(sprint_id):
    """Re-run the async content worker for a sprint whose generation failed.

    POST-only (a GET must never have side effects). Idempotent: the worker
    only fills empty payloads, so a retry on a healthy sprint is a no-op and a
    retry after the LLM recovers heals the generation_error markers. Runs on a
    background thread — the dashboard re-polls /generation for the result.
    """
    gate = require_login()
    if gate:
        return gate
    sb = obtain_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return jsonify({"error": "not found"}), 404

    import threading
    from flask import current_app
    from routes.main import _generate_in_background
    app = current_app._get_current_object()
    threading.Thread(
        target=_generate_in_background, args=(app, sprint_id), daemon=True,
    ).start()
    return jsonify({"status": "generating", "generated": None, "total": 14})


def _complete_day_if_not_done(sb, sprint, day_no):
    """Complete a day if not already done. Returns dict with status and meter.
    Idempotent: double-clicking complete is a no-op."""
    day_row = sb.table("sprint_days").select("is_done") \
        .eq("sprint_id", sprint["id"]).eq("day_no", day_no).limit(1).execute().data
    if day_row and day_row[0].get("is_done"):
        return {"already_done": True, "meter": None}

    sb.table("sprint_days").update({"is_done": True}) \
        .eq("sprint_id", sprint["id"]).eq("day_no", day_no).execute()

    next_day = min(day_no + 1, 14)
    phase = "A" if next_day <= 5 else ("B" if next_day <= 10 else "C")
    sb.table("sprints").update({"current_day": next_day, "phase": phase}) \
        .eq("id", sprint["id"]).execute()

    if day_no >= 14:
        sb.table("sprints").update({
            "status": "completed",
            "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }).eq("id", sprint["id"]).execute()

    meter = recompute(sb, sprint["id"], sprint["user_id"], sprint["cluster_key"], day_no)

    mom = load_momentum(sb, sprint["user_id"])
    streak = (mom.get("day_streak") or 0) + 1
    confidence = recompute_confidence(mom.get("confidence"))
    sb.table("user_momentum").upsert({
        "user_id": sprint["user_id"], "day_streak": streak, "confidence": confidence,
    }, on_conflict="user_id").execute()

    return {"already_done": False, "meter": meter, "next_day": next_day}


@sprints_bp.route("/sprints/<sprint_id>/day/<int:day_no>/complete", methods=["POST"])
def complete_day(sprint_id, day_no):
    gate = require_login()
    if gate:
        return gate
    sb = obtain_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return jsonify({"ok": False, "error": "not found"}), 404
    if not load_day(sb, sprint_id, day_no):
        return jsonify({"ok": False, "error": "day not found"}), 404

    result = _complete_day_if_not_done(sb, sprint, day_no)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "meter": result.get("meter"), "next_day": result.get("next_day")})
    if day_no >= 14:
        return redirect(url_for("sprints.dashboard", sprint_id=sprint_id))
    return redirect(url_for("sprints.day", sprint_id=sprint_id, day_no=result.get("next_day", day_no)))




@sprints_bp.route("/sprints/<sprint_id>/day/<int:day_no>/copywork", methods=["POST"])
def submit_copywork(sprint_id, day_no):
    gate = require_login()
    if gate:
        return gate
    sb = obtain_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("sprints.dashboard", sprint_id=sprint_id))

    rubric_url = request.form.get("rubric_url", "").strip()
    if not rubric_url:
        flash("Paste a link to your rebuilt flow before submitting.")
        return redirect(url_for("sprints.day", sprint_id=sprint_id, day_no=day_no))
    if not is_valid_url(rubric_url):
        flash("That doesn't look like a valid link — paste the full URL (starting with http:// or https://).")
        return redirect(url_for("sprints.day", sprint_id=sprint_id, day_no=day_no))
    record_review(sb, sprint_id, "A", status="pending", submitted_url=rubric_url)

    # The submission only counts done when the learner ticked every rubric item
    # BEFORE submitting (content-quality P0-3: the rubric never auto-passes
    # itself — a pasted URL alone unlocks nothing). Then auto-check Gate A:
    # all 3 projects done + self-checked + URLs → pass → Phase B unlocks.
    project_index = DAY_TO_PROJECT.get(day_no)
    if project_index:
        proj_rows = sb.table("copywork_projects").select("rubric_checked,rubric") \
            .eq("sprint_id", sprint_id).eq("project_index", project_index).limit(1).execute().data
        rubric_checked = list((proj_rows[0].get("rubric_checked") if proj_rows else None) or [])
        rubric_items = list((proj_rows[0].get("rubric") if proj_rows else None) or [])
        if len(rubric_items) < 3:
            # Generation failed for this day — there is nothing to tick, and
            # "tick all three" would be a lie (dogfood #1: Gate A unwinnable
            # on empty rubric rows). Tell the truth and point at the repair.
            flash("This day's checklist hasn't finished generating, so the build "
                  "can't be verified yet — use “Retry generation” on the task tab, "
                  "then tick the rubric and submit again.")
            return redirect(url_for("sprints.day", sprint_id=sprint_id, day_no=day_no))
        all_ticked = len(rubric_checked) >= 3 and all(rubric_checked)
        sb.table("copywork_projects").update({
            "done": all_ticked,
            "submitted_url": rubric_url,
            "rubric_checked": [bool(c) for c in rubric_checked],
        }).eq("sprint_id", sprint_id).eq("project_index", project_index).execute()
        if not all_ticked:
            flash("Tick off all three rubric items before submitting — "
                  "your build only counts once you've self-checked it.")
    auto_check_gate_a(sb, sprint_id, submitted_url=rubric_url)
    return redirect(url_for("sprints.day", sprint_id=sprint_id, day_no=day_no))


@sprints_bp.route("/sprints/<sprint_id>/day/<int:day_no>/rubric-check", methods=["POST"])
def rubric_check(sprint_id, day_no):
    """Toggle a rubric item check for a copy-work project."""
    gate = require_login()
    if gate:
        return gate
    sb = obtain_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("sprints.dashboard", sprint_id=sprint_id))

    project_index = request.form.get("project_index", type=int)
    rubric_index = request.form.get("rubric_index", type=int)
    checked = request.form.get("checked") == "true"

    if project_index is None or rubric_index is None:
        return jsonify({"ok": False, "error": "Missing project_index or rubric_index"}), 400

    # Get the project's current rubric_checked state
    project = sb.table("copywork_projects").select("rubric_checked") \
        .eq("sprint_id", sprint_id).eq("project_index", project_index).limit(1).execute().data

    if not project:
        return jsonify({"ok": False, "error": "Project not found"}), 404

    rubric_checked = project[0].get("rubric_checked") or [False, False, False]
    if rubric_index < 0 or rubric_index >= len(rubric_checked):
        return jsonify({"ok": False, "error": "Invalid rubric_index"}), 400

    rubric_checked[rubric_index] = checked

    sb.table("copywork_projects").update({"rubric_checked": rubric_checked}) \
        .eq("sprint_id", sprint_id).eq("project_index", project_index).execute()

    return jsonify({"ok": True, "rubric_checked": rubric_checked})


@sprints_bp.route("/sprints/<sprint_id>/day/<int:day_no>/gapfill-check", methods=["POST"])
def gapfill_check(sprint_id, day_no):
    """Toggle gap-fill addressed status for a day."""
    gate = require_login()
    if gate:
        return gate
    sb = obtain_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("sprints.dashboard", sprint_id=sprint_id))

    checked = request.form.get("checked") == "true"

    # Update the sprint_days row for this day
    sb.table("sprint_days").update({"gap_fill_done": checked}) \
        .eq("sprint_id", sprint_id).eq("day_no", day_no).execute()

    return jsonify({"ok": True, "gap_fill_done": checked})


@sprints_bp.route("/sprints/<sprint_id>/complete", methods=["POST"])
def complete(sprint_id):
    """Explicit sprint completion — only after BOTH gates passed. The old
    version flipped status on one click from Day 1 and the dashboard then
    claimed a badge that was never minted (dogfood blocker #2): completion
    must mean the work, not the button."""
    gate = require_login()
    if gate:
        return gate
    sb = obtain_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("main.dashboard"))
    if not gate_a_passed(sb, sprint_id):
        flash("Not yet — Gate A (three verified copy-work builds) must pass "
              "before your sprint can be completed.")
        return redirect(url_for("sprints.dashboard", sprint_id=sprint_id))
    if not gate_b_passed(sb, sprint_id):
        flash("Not yet — your Mock Contract deliverable must pass Gate B "
              "verification before the sprint is complete.")
        return redirect(url_for("sprints.dashboard", sprint_id=sprint_id))
    sb.table("sprints").update({
        "status": "completed",
        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }).eq("id", sprint_id).execute()
    return redirect(url_for("sprints.dashboard", sprint_id=sprint_id))


@sprints_bp.route("/sprints/<sprint_id>/badge")
def badge(sprint_id):
    gate = require_login()
    if gate:
        return gate
    sb = obtain_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("main.dashboard"))
    issue_badge(sb, sprint_id, sprint["user_id"], sprint["cluster_key"])
    return redirect(url_for("sprints.dashboard", sprint_id=sprint_id))
