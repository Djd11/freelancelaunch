"""sprints blueprint — dashboard, day view, day completion, verification, badge (arch §4.2)."""
import datetime

from flask import Blueprint, render_template, request, redirect, url_for, g, jsonify, flash

from routes import (require_login, load_cluster, load_sprint, load_cohort,
                    load_meter, load_momentum, load_day, load_project, phase_a_done_days)
from services.supabase_client import get_supabase
from services.verification_service import gate_a_passed, gate_b_passed, record as record_review
from services.verification_service import auto_check_gate_a, is_valid_url
from services.unlock_engine import recompute
from services.badge_engine import issue as issue_badge
from services.nudge_engine import nudge as nudge_for, recompute_confidence

sprints_bp = Blueprint("sprints", __name__)

# Day → copy-work project index (1-based). Mockup: Day 4 = Project 2 (Abandoned-Cart).
# All four Phase A copy-work days (2-5) must map — project 3 lives on Day 5, or
# Gate A can never pass through the real day flow (content-quality C1).
DAY_TO_PROJECT = {2: 1, 3: 1, 4: 2, 5: 3}


@sprints_bp.route("/sprints/<sprint_id>")
def dashboard(sprint_id):
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
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
    nudge = nudge_for(sprint, momentum)
    contracts = sb.table("contracts").select("*").eq("sprint_id", sprint_id).execute().data

    return render_template(
        "sprint_dashboard.html",
        sprint=sprint, cluster=cluster, cohort=cohort, meter=meter,
        momentum=momentum, today=today, phase_a_days=phase_a_days,
        gate_a_pass=gate_a_passed(sb, sprint_id),
        gate_b_pass=gate_b_passed(sb, sprint_id),
        nudge=nudge, contracts=contracts,
    )


@sprints_bp.route("/sprints/<sprint_id>/day/<int:day_no>")
def day(sprint_id, day_no):
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
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
    from services.lesson_engine import generation_error
    lesson = payload.get("lesson")
    gen_error = payload.get("generation_error") or generation_error(sb, sprint_id)
    clone_steps = (project or {}).get("clone_steps") or []
    rubric = (project or {}).get("rubric") or []

    return render_template(
        "day.html",
        sprint=sprint, day=day_row, project=project, meter=meter,
        day_done=bool(day_row.get("is_done")), gap_fill_topic=gap_fill_topic, pct=pct,
        lesson=lesson, gen_error=gen_error, clone_steps=clone_steps, rubric=rubric,
    )


@sprints_bp.route("/sprints/<sprint_id>/generation")
def generation(sprint_id):
    """Content-generation progress — the populated lesson payload count IS the
    DB-backed log (arch §7). Polled by the dashboard spinner."""
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return jsonify({"error": "not found"}), 404
    from services.lesson_engine import generation_progress, generation_error
    generated, total = generation_progress(sb, sprint_id)
    err = generation_error(sb, sprint_id)
    if err:
        return jsonify({
            "status": "error",
            "error": err,
            "generated": generated,
            "total": total,
        })
    return jsonify({
        "status": "ready" if generated >= total else "generating",
        "generated": generated,
        "total": total,
    })


@sprints_bp.route("/sprints/<sprint_id>/day/<int:day_no>/complete", methods=["POST"])
def complete_day(sprint_id, day_no):
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return jsonify({"ok": False, "error": "not found"}), 404

    # A day number outside 1..14 (or a day with no row) must never advance or
    # complete the sprint — refuse it (negative-path hardening, api.feature).
    if not load_day(sb, sprint_id, day_no):
        return jsonify({"ok": False, "error": "day not found"}), 404

    sb.table("sprint_days").update({"is_done": True}).eq("sprint_id", sprint_id).eq("day_no", day_no).execute()

    next_day = min(day_no + 1, 14)
    phase = "A" if next_day <= 5 else ("B" if next_day <= 10 else "C")
    sb.table("sprints").update({"current_day": next_day, "phase": phase}).eq("id", sprint_id).execute()

    # Day 14 done = the sprint is completed (eng-spec §3 J7: badge after the
    # sprint completes) — completed_at stamps the finish.
    if day_no >= 14:
        sb.table("sprints").update({
            "status": "completed",
            "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }).eq("id", sprint_id).execute()

    meter = recompute(sb, sprint_id, sprint["user_id"], sprint["cluster_key"], day_no)

    # momentum: streak +1, confidence recomputed by the nudge engine (eng-spec §4.4)
    mom = load_momentum(sb, sprint["user_id"])
    streak = (mom.get("day_streak") or 0) + 1
    confidence = recompute_confidence(mom.get("confidence"))
    sb.table("user_momentum").upsert({
        "user_id": sprint["user_id"], "day_streak": streak, "confidence": confidence,
    }, on_conflict="user_id").execute()

    return jsonify({
        "ok": True,
        "next_day": next_day,
        "meter": meter,
        "momentum": {"day_streak": streak, "confidence": confidence},
    })


@sprints_bp.route("/sprints/<sprint_id>/day/<int:day_no>/copywork", methods=["POST"])
def submit_copywork(sprint_id, day_no):
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
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

    # Mark the day's copy-work project done (storing the submitted URL on the
    # project row), then auto-check Gate A: all 3 projects done with URLs →
    # pass → Phase B unlocks (eng-spec §4.2).
    project_index = DAY_TO_PROJECT.get(day_no)
    if project_index:
        sb.table("copywork_projects").update({"done": True, "submitted_url": rubric_url}) \
            .eq("sprint_id", sprint_id).eq("project_index", project_index).execute()
    auto_check_gate_a(sb, sprint_id, submitted_url=rubric_url)
    return redirect(url_for("sprints.day", sprint_id=sprint_id, day_no=day_no))


@sprints_bp.route("/sprints/<sprint_id>/complete", methods=["POST"])
def complete(sprint_id):
    """Explicit sprint completion (Day 14 or the learner's own call)."""
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("main.dashboard"))
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
    sb = get_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return redirect(url_for("main.dashboard"))
    issue_badge(sb, sprint_id, sprint["user_id"], sprint["cluster_key"])
    return redirect(url_for("sprints.dashboard", sprint_id=sprint_id))
