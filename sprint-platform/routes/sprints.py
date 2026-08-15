"""sprints blueprint — dashboard, day view, day completion, verification, badge (arch §4.2)."""
from flask import Blueprint, render_template, request, redirect, url_for, g, jsonify

from routes import (require_login, load_cluster, load_sprint, load_cohort,
                    load_meter, load_momentum, load_day, load_project, phase_a_done_days)
from services.supabase_client import get_supabase
from services.verification_service import gate_a_passed, gate_b_passed, record as record_review
from services.unlock_engine import recompute
from services.badge_engine import issue as issue_badge
from services.nudge_engine import nudge as nudge_for

sprints_bp = Blueprint("sprints", __name__)

# Day → copy-work project index (1-based). Mockup: Day 4 = Project 2 (Abandoned-Cart).
DAY_TO_PROJECT = {2: 1, 3: 1, 4: 2}


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

    return render_template(
        "sprint_dashboard.html",
        sprint=sprint, cluster=cluster, cohort=cohort, meter=meter,
        momentum=momentum, today=today, phase_a_days=phase_a_days,
        gate_a_pass=gate_a_passed(sb, sprint_id),
        gate_b_pass=gate_b_passed(sb, sprint_id),
        nudge=nudge,
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

    return render_template(
        "day.html",
        sprint=sprint, day=day_row, project=project, meter=meter,
        day_done=bool(day_row.get("is_done")), gap_fill_topic=gap_fill_topic, pct=pct,
    )


@sprints_bp.route("/sprints/<sprint_id>/day/<int:day_no>/complete", methods=["POST"])
def complete_day(sprint_id, day_no):
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return jsonify({"ok": False, "error": "not found"}), 404

    sb.table("sprint_days").update({"is_done": True}).eq("sprint_id", sprint_id).eq("day_no", day_no).execute()

    next_day = min(day_no + 1, 14)
    phase = "A" if next_day <= 5 else ("B" if next_day <= 10 else "C")
    sb.table("sprints").update({"current_day": next_day, "phase": phase}).eq("id", sprint_id).execute()

    meter = recompute(sb, sprint_id, sprint["user_id"], sprint["cluster_key"], day_no)

    # momentum: streak +1, confidence up (rule-based)
    mom = load_momentum(sb, sprint["user_id"])
    streak = (mom.get("day_streak") or 0) + 1
    confidence = min(100, (mom.get("confidence") or 50) + 3)
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

    rubric_url = request.form.get("rubric_url", "")
    record_review(sb, sprint_id, "A", status="pending", submitted_url=rubric_url or None)
    return redirect(url_for("sprints.day", sprint_id=sprint_id, day_no=day_no))


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
