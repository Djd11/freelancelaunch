"""
lesson_engine — LLM-generated lesson + copy-work content (eng-spec §3 J4, §5, arch §4.3).

Every day's Watch · Lesson and every copy-work project's anatomy (clone steps +
rubric) is generated from the cluster's live job posting via the shared LLM
provider chain (services/llm.py). Content is LLM-only: there are no
deterministic content fallbacks. When the chain returns None or the output
cannot be parsed, the worker records a `generation_error` marker on the day's
action_payload and the UI surfaces it — the learner never sees template content
masquerading as generated content.

Progress model: a sprint's content is "ready" when all 14 sprint_days carry a
non-empty action_payload.lesson. The worker writes each day as it completes, so
the count of populated payloads IS the progress log (arch §7: DB is the source
of truth) — no extra table or column needed.
"""
import json
import re

from services.llm import call_llm, LLMGenerationError

# Day → copy-work project index (1-based). Mirrors routes/sprints.DAY_TO_PROJECT.
# Every Phase A copy-work day (2-5) must map so project 3 is reachable.
DAY_TO_PROJECT = {2: 1, 3: 1, 4: 2, 5: 3}


def _excerpt(text, limit=220):
    if not text:
        return ""
    text = " ".join((text or "").split())
    return text[:limit].rstrip() + ("…" if len(text) > limit else "")


def _top_job(sb, cluster_key):
    """First active posting in the cluster (same pick as mock_contract_engine)."""
    feed = sb.table("job_feed").select("*") \
        .eq("cluster_key", cluster_key).eq("status", "active") \
        .order("unlock_day").order("id").limit(1).execute().data
    if feed:
        return feed[0]
    feed = sb.table("job_feed").select("*").eq("status", "active") \
        .order("unlock_day").order("id").limit(1).execute().data
    return feed[0] if feed else None


# ─── LLM prompt + parsing ─────────────────────────────────────────────

def _lesson_prompt(job, day, action_type, project_title, gap_fill_topic=None):
    job_title = (job or {}).get("title") or "the target job"
    excerpt = _excerpt((job or {}).get("description") or "")
    prompt = (
        "You generate one micro-lesson for a 14-day freelancer sprint. "
        f"Cluster job posting: \"{job_title}\". "
        f"Posting text: \"{excerpt}\". "
        f"Day {day} ({action_type}). Project: {project_title}. "
        "Write a 100-150 word lesson script that teaches the learner to rebuild "
        "exactly what the posting asks, using the posting's own terminology. "
        'Reply with JSON only: {"title": "...", "script": "...", "key_points": ["...", "..."]}.'
    )
    if gap_fill_topic:
        prompt += f" Gap-fill focus: {gap_fill_topic}."
    return prompt


def _load_json_object(text):
    """Lenient JSON extraction — find the first {...} block and load it."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _parse_json(text):
    """Lesson-shape parser — title/script/key_points from the raw LLM dict."""
    data = _load_json_object(text)
    if not data:
        return None
    return {
        "title": str(data.get("title") or "").strip(),
        "script": str(data.get("script") or "").strip(),
        "key_points": [str(k) for k in (data.get("key_points") or []) if str(k).strip()],
    }


def _project_prompt(job, project_index):
    job_title = (job or {}).get("title") or "the target job"
    excerpt = _excerpt((job or {}).get("description") or "")
    return (
        "You design a copy-work replication task for a freelancer sprint. "
        f"Cluster job posting: \"{job_title}\". Posting text: \"{excerpt}\". "
        f"Design replication project {project_index} of 3: an exact clone of the "
        "anatomy the posting describes. "
        'Reply with JSON only: {"title": "...", "clone_steps": ["...", "..."], '
        '"rubric": ["...", "...", "..."], "gap_fill_topic": "..." or null}. '
        "clone_steps = 3-5 concrete build steps; rubric = 3 auto-checkable acceptance criteria."
    )


def _parse_project(text):
    """Project-anatomy parser — the raw LLM dict keeps clone_steps/rubric (the
    lesson-shape _parse_json would drop them)."""
    data = _load_json_object(text)
    if not data or not data.get("title"):
        raise LLMGenerationError("LLM returned unparseable project anatomy")
    return {
        "title": str(data.get("title") or "").strip(),
        "clone_steps": [str(s) for s in (data.get("clone_steps") or []) if str(s).strip()],
        "rubric": [str(r) for r in (data.get("rubric") or []) if str(r).strip()],
        "gap_fill_topic": data.get("gap_fill_topic"),
    }


# ─── Generation (per day / per project) ───────────────────────────────

def _gap_fill_topic(sb, sprint_id):
    """The nuance flagged on any copy-work project of the sprint — Day 5's
    targeted micro-lesson focus (eng-spec J4, research: Day 5 = The Gap Fill)."""
    rows = sb.table("copywork_projects").select("gap_fill_topic") \
        .eq("sprint_id", sprint_id).execute().data
    for r in rows:
        if r.get("gap_fill_topic"):
            return r["gap_fill_topic"]
    return None


def lesson_for_day(sb, sprint, day_row, project, gap_fill_topic=None):
    """Generate the day's Watch · Lesson content from the LLM (LLM-only).

    Returns a dict {"title", "script", "key_points"} ready to store in
    sprint_days.action_payload.lesson. Day 5 is the targeted gap-fill
    micro-lesson on the flagged nuance when one exists — the topic is passed to
    the LLM so the lesson is written for it, never templated.

    Raises LLMGenerationError when no provider answered or the output was not
    usable JSON — callers must surface the error, never substitute templates.
    """
    job = _top_job(sb, sprint.get("cluster_key"))
    if day_row.get("day_no") == 5 and not gap_fill_topic:
        gap_fill_topic = _gap_fill_topic(sb, sprint.get("id"))
    project_title = (project or {}).get("title") or day_row.get("title") or ""
    text = call_llm(_lesson_prompt(job, day_row.get("day_no"), day_row.get("action_type"),
                                   project_title, gap_fill_topic), timeout=15)
    if not text:
        raise LLMGenerationError("No LLM provider answered for the day's lesson")
    parsed = _parse_json(text)
    if not parsed or not parsed.get("script"):
        raise LLMGenerationError("LLM returned an unusable lesson (missing script)")
    return {
        "title": parsed["title"],
        "script": parsed["script"],
        "key_points": parsed["key_points"] or [],
    }


def project_anatomy(sb, sprint, project_index):
    """Generate one copy-work project's clone_steps + rubric (LLM-only)."""
    job = _top_job(sb, sprint.get("cluster_key"))
    text = call_llm(_project_prompt(job, project_index), timeout=15)
    if not text:
        raise LLMGenerationError("No LLM provider answered for the project anatomy")
    return _parse_project(text)


# ─── The async worker ─────────────────────────────────────────────────

def _mark_generation_error(sb, sprint_id, message):
    """Stamp the generation failure on a day's payload so the UI can show it.

    Writes to the first day that has no lesson yet (or day 1 as a last resort)
    — the DB is the source of truth, and no schema change is needed.
    """
    days = sb.table("sprint_days").select("day_no,action_payload") \
        .eq("sprint_id", sprint_id).order("day_no").execute().data
    target = None
    for d in days:
        payload = d.get("action_payload") or {}
        if not payload.get("lesson"):
            target = d
            break
    if target is None and days:
        target = days[0]
    if target is None:
        return
    payload = dict(target.get("action_payload") or {})
    payload["generation_error"] = message
    sb.table("sprint_days").update({"action_payload": payload}) \
        .eq("sprint_id", sprint_id).eq("day_no", target["day_no"]).execute()


def generate_sprint_content(sb, sprint_id):
    """Fill every day's lesson payload + every project's anatomy for a sprint.

    Runs on a background thread (routes/main.py start_sprint). Each day/project
    is written to the DB as it completes — the populated-payload count is the
    progress the frontend polls. Idempotent: only fills empty payloads.

    Content is LLM-only: on failure the worker stamps a visible
    `generation_error` on a day payload and re-raises; the frontend's
    /generation polling and day view surface it instead of endless "generating".
    """
    try:
        sprint_rows = sb.table("sprints").select("*").eq("id", sprint_id).limit(1).execute().data
        if not sprint_rows:
            return
        sprint = sprint_rows[0]
        cluster_key = sprint.get("cluster_key", "email-automation")

        days = sb.table("sprint_days").select("*").eq("sprint_id", sprint_id).order("day_no").execute().data
        for day_row in days:
            payload = day_row.get("action_payload") or {}
            if payload.get("lesson"):
                continue  # already generated
            project_index = (payload or {}).get("project_index") or DAY_TO_PROJECT.get(day_row.get("day_no"))
            project = None
            if project_index:
                proj = sb.table("copywork_projects").select("*") \
                    .eq("sprint_id", sprint_id).eq("project_index", project_index).limit(1).execute().data
                project = proj[0] if proj else None
            lesson = lesson_for_day(sb, sprint, day_row, project)
            new_payload = dict(payload)
            new_payload.pop("generation_error", None)  # a successful retry heals the marker
            new_payload["lesson"] = lesson
            # Two-panel voiceover (D8: kinetic text + TTS): generate edge-tts MP3
            # + duration and store on the lesson. Best-effort — if the TTS/Storage
            # pipeline can't run, the lesson still renders as kinetic text.
            try:
                from services.video_engine import voiceover_for_lesson
                vo = voiceover_for_lesson(sb, sprint_id, day_row["day_no"], lesson)
                if vo:
                    new_payload["lesson"]["voiceover"] = vo
            except Exception:
                pass
            sb.table("sprint_days").update({"action_payload": new_payload}) \
                .eq("sprint_id", sprint_id).eq("day_no", day_row["day_no"]).execute()

        for index in (1, 2, 3):
            existing = sb.table("copywork_projects").select("id,clone_steps,title") \
                .eq("sprint_id", sprint_id).eq("project_index", index).limit(1).execute().data
            if not existing:
                continue
            row = existing[0]
            if row.get("clone_steps"):
                continue  # anatomy already generated
            anatomy = project_anatomy(sb, sprint, index)
            sb.table("copywork_projects").update({
                "title": anatomy["title"],
                "clone_steps": anatomy["clone_steps"],
                "rubric": anatomy["rubric"],
                "gap_fill_topic": anatomy["gap_fill_topic"],
            }).eq("sprint_id", sprint_id).eq("project_index", index).execute()
    except LLMGenerationError as exc:
        # LLM-only: never substitute templates — record the failure so the UI
        # surfaces it, then propagate for logging.
        _mark_generation_error(sb, sprint_id, str(exc))
        raise


def generation_progress(sb, sprint_id):
    """(generated, total) — count of days whose lesson payload is populated."""
    days = sb.table("sprint_days").select("action_payload").eq("sprint_id", sprint_id).execute().data
    total = len(days) or 14
    generated = sum(1 for d in days if (d.get("action_payload") or {}).get("lesson"))
    return generated, total


def generation_error(sb, sprint_id):
    """The first recorded generation failure for the sprint, or None."""
    days = sb.table("sprint_days").select("action_payload").eq("sprint_id", sprint_id).execute().data
    for d in days:
        err = (d.get("action_payload") or {}).get("generation_error")
        if err:
            return err
    return None
