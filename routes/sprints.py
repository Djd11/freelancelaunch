"""
Sprints routes — Sprint Track (parallel placement path)

Blueprint: `sprints`
Endpoints under /sprints/* and /mentor. Additive to v1; no v1 routes touched.
"""
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from services.supabase_client import get_supabase
from services import (demand_intelligence, unlock_engine, sprint_planner,
                      mock_contract_engine, verification_service,
                      proposal_engine, badge_engine)

logger = logging.getLogger(__name__)
sprints_bp = Blueprint("sprints", __name__)


def _require_user():
    if not g.user:
        return None
    return g.user["id"]


def _get_sprint(sb, sprint_id, user_id):
    resp = sb.table("sprints").select("*").eq("id", sprint_id).eq("user_id", user_id).limit(1).execute()
    return resp.data[0] if resp.data else None


# ─── sprint track landing (entry point) ───────────────────────────────

@sprints_bp.route("/sprints")
def landing():
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("auth.login"))
    sb = get_supabase()

    # active / past sprints for this user
    my_sprints = sb.table("sprints").select("*") \
        .eq("user_id", user_id).order("created_at").execute().data or []

    # live demand clusters for the start form (seeded on demand)
    clusters = [
        {"key": "email-automation", "display_name": "Email Automation"},
        {"key": "web-scraping", "display_name": "Web Scraping"},
        {"key": "ai-chatbots", "display_name": "AI Chatbots"},
        {"key": "shopify-dev", "display_name": "Shopify Development"},
        {"key": "data-viz", "display_name": "Data Visualization"},
    ]

    return render_template("sprint/landing.html",
        sprints=my_sprints, clusters=clusters)


# ─── enrollment → plan ────────────────────────────────────────────────

@sprints_bp.route("/sprints/new", methods=["POST"])
def new_sprint():
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("auth.login"))
    slug = (request.form.get("topic") or "email-automation").strip().lower()
    sb = get_supabase()

    # ensure a cluster exists (seed a minimal feed if empty so the meter works)
    cluster = demand_intelligence.resolve_cluster(sb, slug)
    jobs = sb.table("job_feed").select("id", count="exact").eq("cluster_key", slug).limit(1).execute()
    if not (jobs.data or getattr(jobs, "count", 0)):
        # Seed a demo feed for the chosen cluster
        demand_intelligence.ingest_feed(sb, slug, [
            {"title": "Set up email automation for store", "rate": 180, "experience_needed": "entry", "skills": ["klaviyo"]},
            {"title": "Build abandoned-cart recovery flow", "rate": 220, "experience_needed": "entry", "skills": ["klaviyo", "email"]},
            {"title": "Full email lifecycle automation", "rate": 260, "experience_needed": "intermediate", "skills": ["klaviyo", "segments"]},
            {"title": "VIP segmentation & campaign build", "rate": 320, "experience_needed": "intermediate", "skills": ["segments"]},
            {"title": "Multi-step upsell + retention system", "rate": 420, "experience_needed": "expert", "skills": ["klaviyo", "api"]},
            {"title": "Migrate flows & templating audit", "rate": 150, "experience_needed": "entry", "skills": ["email"]},
        ])

    sprint = sb.table("sprints").insert({
        "user_id": user_id,
        "cluster_key": slug,
        "phase": "A",
        "current_day": 1,
        "status": "active",
    }).execute()
    sprint_id = sprint.data[0]["id"]

    sprint_planner.build_plan(sb, sprint_id, slug)
    unlock_engine.recompute(sb, sprint_id, user_id)

    flash(f"Sprint started! Day 1 · Phase A — Copy-Work for {cluster.get('display_name', slug)}", "success")
    return redirect(url_for("sprints.dashboard", sprint_id=sprint_id))


# ─── dashboard ────────────────────────────────────────────────────────

@sprints_bp.route("/sprints/<sprint_id>")
def dashboard(sprint_id):
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("auth.login"))
    sb = get_supabase()
    sprint = _get_sprint(sb, sprint_id, user_id)
    if not sprint:
        flash("Sprint not found", "error")
        return redirect(url_for("dashboard.home"))

    days = sb.table("sprint_days").select("*").eq("sprint_id", sprint_id).order("day_no").execute().data or []
    meter = unlock_engine.read_meter(sb, sprint_id, user_id) or {}
    cluster = demand_intelligence.live_counter(sb, sprint.get("cluster_key"))
    completed = sum(1 for d in days if d.get("is_done"))
    current_day = sprint.get("current_day", 1)

    return render_template("sprint/dashboard.html",
        sprint=sprint, days=days, meter=meter, cluster=cluster,
        completed=completed, current_day=current_day)


# ─── day view + completion (meter uptick) ─────────────────────────────

@sprints_bp.route("/sprints/<sprint_id>/day/<int:day_no>")
def day(sprint_id, day_no):
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("auth.login"))
    sb = get_supabase()
    sprint = _get_sprint(sb, sprint_id, user_id)
    if not sprint:
        return redirect(url_for("dashboard.home"))

    day_resp = sb.table("sprint_days").select("*").eq("sprint_id", sprint_id).eq("day_no", day_no).limit(1).execute()
    day_row = day_resp.data[0] if day_resp.data else None
    phase_gate = {}
    # Phase B gate: brief + verification
    brief = None
    if day_no >= 6:
        brief = mock_contract_engine.create_brief(sb, sprint_id, user_id)
        if day_no >= 11:
            passed = verification_service.is_passed(sb, sprint_id, user_id)
            phase_gate["phase_c_locked"] = not passed

    return render_template("sprint/day.html",
        sprint=sprint, day=day_row, day_no=day_no, brief=brief, phase_gate=phase_gate)


@sprints_bp.route("/sprints/<sprint_id>/day/<int:day_no>/complete", methods=["POST"])
def complete_day(sprint_id, day_no):
    user_id = _require_user()
    if not user_id:
        return jsonify({"ok": False, "error": "not logged in"}), 401
    sb = get_supabase()

    sb.table("sprint_days").update({"is_done": True, "completed_at": "now()"}) \
        .eq("sprint_id", sprint_id).eq("day_no", day_no).execute()

    # advance current_day + phase
    next_day = day_no + 1
    new_phase = sprint_planner.phase_for_day(next_day)
    sb.table("sprints").update({"current_day": next_day, "phase": new_phase}) \
        .eq("id", sprint_id).execute()

    # the meter uptick — the core motivational moment
    meter = unlock_engine.recompute(sb, sprint_id, user_id)

    return jsonify({"ok": True, "day_no": day_no, "next_day": next_day,
                    "meter": meter or {}})


# ─── mock contract submit ─────────────────────────────────────────────

@sprints_bp.route("/sprints/<sprint_id>/contract", methods=["GET"])
def contract(sprint_id):
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("auth.login"))
    sb = get_supabase()
    sprint = _get_sprint(sb, sprint_id, user_id)
    brief = mock_contract_engine.create_brief(sb, sprint_id, user_id)
    review = None
    if brief:
        rev = sb.table("verification_reviews").select("*") \
            .eq("capstone_brief_id", brief["id"]).eq("user_id", user_id).limit(1).execute()
        review = rev.data[0] if rev.data else None
    return render_template("sprint/contract.html", sprint=sprint, brief=brief, review=review)


@sprints_bp.route("/sprints/<sprint_id>/contract/submit", methods=["POST"])
def contract_submit(sprint_id):
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("auth.login"))
    sb = get_supabase()
    brief = mock_contract_engine.create_brief(sb, sprint_id, user_id)
    if not brief:
        flash("No active brief", "error")
        return redirect(url_for("sprints.contract", sprint_id=sprint_id))
    submission_url = (request.form.get("submission_url") or "").strip()
    if not submission_url:
        flash("Paste a link to your deliverable", "error")
        return redirect(url_for("sprints.contract", sprint_id=sprint_id))
    result = verification_service.submit(sb, brief["id"], user_id, submission_url)
    flash(result["feedback"], "success" if result["status"] == "pass" else "info")
    return redirect(url_for("sprints.contract", sprint_id=sprint_id))


# ─── proposals / first-bid ────────────────────────────────────────────

@sprints_bp.route("/sprints/<sprint_id>/proposals")
def proposals(sprint_id):
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("auth.login"))
    sb = get_supabase()
    sprint = _get_sprint(sb, sprint_id, user_id)

    # First-Bid challenge: 5 live jobs → generate drafts
    jobs = sb.table("job_feed").select("*").eq("cluster_key", sprint.get("cluster_key")) \
        .eq("status", "active").order("unlock_day").limit(5).execute().data or []
    drafts = []
    for j in jobs:
        p = proposal_engine.generate(sb, sprint_id, user_id, j["id"])
        if p:
            p["job_title"] = j["title"]
            p["rate"] = j.get("rate")
            drafts.append(p)
    submitted = sum(1 for p in drafts if p.get("status") == "submitted")
    return render_template("sprint/proposals.html",
        sprint=sprint, drafts=drafts, submitted=submitted, target=5)


@sprints_bp.route("/sprints/<sprint_id>/proposals/<proposal_id>/submit", methods=["POST"])
def proposal_submit(sprint_id, proposal_id):
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("auth.login"))
    sb = get_supabase()
    proposal_engine.mark_submitted(sb, proposal_id)
    sb.table("freelance_pipeline").update({"proposals_sent": "proposals_sent + 1"}) \
        .eq("user_id", user_id).execute()
    flash("Proposal marked submitted — great work!", "success")
    return redirect(url_for("sprints.proposals", sprint_id=sprint_id))


# ─── badge ────────────────────────────────────────────────────────────

@sprints_bp.route("/sprints/<sprint_id>/badge")
def badge(sprint_id):
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("auth.login"))
    sb = get_supabase()
    sprint = _get_sprint(sb, sprint_id, user_id)
    badge = badge_engine.issue(sb, sprint_id, user_id)
    badges = badge_engine.for_user(sb, user_id)
    return render_template("sprint/badge.html", sprint=sprint, badge=badge, badges=badges)
