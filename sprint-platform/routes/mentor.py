"""mentor blueprint — job-grounded Socratic chat (eng-spec §3 J8, arch §4.2)."""
from flask import Blueprint, render_template, request, redirect, url_for, g, jsonify

from routes import require_login, load_sprint
from services.supabase_client import get_supabase
from services.mentor_agent import answer as mentor_answer
from services.llm import LLMGenerationError

mentor_bp = Blueprint("mentor", __name__)


def _context(sb, user_id):
    """Gather the mentor's context: the user's active sprint + target job.
    
    The target job is resolved from the sprint's capstone brief (job_feed_id).
    If no capstone brief exists, falls back to the first job in the cluster
    (ordered by id for determinism).
    """
    sprints = sb.table("sprints").select("*").eq("user_id", user_id).eq("status", "active").execute().data
    sprint = sprints[0] if sprints else None
    job = None
    job_id = None
    if sprint:
        # Try to find the target job via the sprint's capstone brief
        briefs = sb.table("capstone_briefs").select("job_feed_id").eq("sprint_id", sprint["id"]).limit(1).execute().data
        if briefs and briefs[0].get("job_feed_id"):
            target_id = briefs[0]["job_feed_id"]
            job = sb.table("job_feed").select("*").eq("id", target_id).limit(1).execute().data
            if job:
                job = job[0]
                job_id = job["id"]
        # Fallback: first job in the cluster, ordered by unlock_day then id
        # for determinism (id-only ordering is insertion-order dependent).
        if not job:
            jobs = sb.table("job_feed").select("*").eq("cluster_key", sprint["cluster_key"]).order("unlock_day").order("id").limit(1).execute().data
            if jobs:
                job = jobs[0]
                job_id = job["id"]
    return sprint, job, job_id


@mentor_bp.route("/mentor")
def chat():
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    sprint, job, job_id = _context(sb, g.user["id"])
    cluster_name = "a sprint"
    progress = 0
    job_desc = ""
    if sprint:
        cluster_rows = sb.table("job_clusters").select("display_name").eq("cluster_key", sprint["cluster_key"]).limit(1).execute().data
        cluster_name = cluster_rows[0]["display_name"] if cluster_rows else "your sprint"
        progress = round(((sprint.get("current_day") or 1) - 1) / 14 * 100)
    if job:
        job_desc = job.get("description") or ""
    if job_id:
        context_line = f"📌 Context: job #{job_id} · {cluster_name} · progress {progress}%"
    else:
        context_line = "📌 Context: your active sprint"
    day_no = (sprint or {}).get("current_day") or 1
    intro = (
        f"You're on Day {day_no} of {cluster_name}. "
        f"Your target job says: \"{(job_desc or 'an anonymized live posting')[:80]}\" — "
        f"what's one part you're unsure about?"
    )
    # Replay the last few recorded turns so the chat shows the actual exchange
    # (the turn endpoint persists to mentor_sessions; the page renders them).
    sessions = sb.table("mentor_sessions").select("turn_json") \
        .eq("user_id", g.user["id"]).order("created_at", desc=True).limit(5).execute().data
    history = []
    for s in reversed(sessions):
        for turn in s.get("turn_json") or []:
            if turn.get("question"):
                history.append({"role": "user", "text": turn["question"]})
            if turn.get("answer"):
                history.append({"role": "mentor", "text": turn["answer"]})
    return render_template("mentor.html", messages=[
        {"role": "mentor", "text": intro, "context": context_line},
    ] + history)


@mentor_bp.route("/mentor/turn", methods=["POST"])
def turn():
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()

    data = request.get_json(silent=True) or {}
    question = data.get("question") or request.form.get("question", "")
    if not question:
        return jsonify({"answer": "Ask me anything about your target job.", "guided": True}), 200

    sprint, job, job_id = _context(sb, g.user["id"])
    job_desc = job.get("description") or "" if job else ""
    try:
        result = mentor_answer(question, job_desc)
    except LLMGenerationError as exc:
        # LLM-only mentor: no deterministic template. Surface the failure
        # visibly (503) instead of answering with canned content.
        return jsonify({"error": str(exc), "guided": True}), 503

    # Record the session scoped to the user's sprint + target job.
    sb.table("mentor_sessions").insert({
        "user_id": g.user["id"],
        "sprint_id": sprint["id"] if sprint else None,
        "job_feed_id": job_id,
        "turn_json": [{"question": question, "answer": result["answer"]}],
    }).execute()

    return jsonify(result), 200
