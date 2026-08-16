"""
lesson_engine — LLM-generated lesson + copy-work content (eng-spec §3 J4, §5, arch §4.3).

Every day's Watch · Lesson and every copy-work project's anatomy (clone steps +
rubric) is generated from the cluster's live job posting via the shared LLM
fallback chain (services/llm.py). When the chain returns None (no keys yet,
provider down), a deterministic job-grounded template fills in — No-500
philosophy, and the content never blocks a request (async worker, DB-backed).

Progress model: a sprint's content is "ready" when all 14 sprint_days carry a
non-empty action_payload.lesson. The worker writes each day as it completes, so
the count of populated payloads IS the progress log (arch §7: DB is the source
of truth) — no extra table or column needed.
"""
import json
import re

from services.llm import call_llm

# ─── Deterministic fallbacks (offline-safe, same strings the mockup shows) ───

ACTION_LABELS = {
    "setup": "setup your workspace and watch the flow anatomy",
    "copywork": "rebuild a real flow from scratch",
    "contract": "execute the mock contract like it is paid",
    "case-study": "write the Problem / Solution / Result case study",
    "proposal": "send a proposal against a live posting",
}

DEFAULT_STEPS = [
    "Trigger on Checkout Started",
    "2-step sequence: 30 min + 24 hr delays",
    "Cart summary dynamic block",
    "Coupon at step 2 (10% off)",
]

DEFAULT_RUBRIC = [
    "Flow is built from a blank account",
    "Trigger + dynamic block are present",
    "Deliverable matches the brief's acceptance criteria",
]

# Day → copy-work project index (1-based). Mirrors routes/sprints.DAY_TO_PROJECT.
DAY_TO_PROJECT = {2: 1, 3: 1, 4: 2}


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


def _fallback_lesson(job, day, action_type, project_title):
    """Deterministic job-grounded lesson — echoes the real posting's wording."""
    job_title = (job or {}).get("title") or "the target job"
    excerpt = _excerpt((job or {}).get("description") or "")
    label = ACTION_LABELS.get(action_type, action_type)
    title = f"{job_title}: how to {label}"
    script = (
        f"Your target job is '{job_title}'. Today (Day {day}) you {label}. "
        "Read the posting's own words and rebuild the smallest real version of "
        "what it asks for — not a generic tutorial version."
    )
    if excerpt:
        script += f" The posting says: \"{excerpt}\". Match that vocabulary."
    key_points = [
        f"What the posting literally asks for in {job_title}",
        "The smallest reproducible piece you can build today",
        "How your deliverable maps to the posting's wording",
    ]
    return {"title": title, "script": script, "key_points": key_points}


# ─── LLM prompt + parsing ─────────────────────────────────────────────

def _lesson_prompt(job, day, action_type, project_title):
    job_title = (job or {}).get("title") or "the target job"
    excerpt = _excerpt((job or {}).get("description") or "")
    return (
        "You generate one micro-lesson for a 14-day freelancer sprint. "
        f"Cluster job posting: \"{job_title}\". "
        f"Posting text: \"{excerpt}\". "
        f"Day {day} ({action_type}). Project: {project_title}. "
        "Write a 100-150 word lesson script that teaches the learner to rebuild "
        "exactly what the posting asks, using the posting's own terminology. "
        'Reply with JSON only: {"title": "...", "script": "...", "key_points": ["...", "..."]}.'
    )


def _parse_json(text):
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
    if not isinstance(data, dict):
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


def _project_fallback(job, project_index):
    """Deterministic project anatomy — mirrors the mockup's project titles."""
    titles = {
        1: "Rebuild the Checkout Welcome Flow",
        2: "Rebuild the Abandoned-Cart Flow",
        3: "Rebuild the Post-Purchase Upsell Flow",
    }
    return {
        "title": titles.get(project_index, f"Rebuild the {project_index} Flow"),
        "clone_steps": list(DEFAULT_STEPS),
        "rubric": list(DEFAULT_RUBRIC),
        "gap_fill_topic": "mobile responsiveness" if project_index == 2 else None,
    }


def _parse_project(text, fallback):
    data = _parse_json(text)
    if not data or not data.get("title"):
        return fallback
    out = {
        "title": data["title"],
        "clone_steps": [str(s) for s in (data.get("clone_steps") or []) if str(s).strip()] or fallback["clone_steps"],
        "rubric": [str(r) for r in (data.get("rubric") or []) if str(r).strip()] or fallback["rubric"],
        "gap_fill_topic": data.get("gap_fill_topic"),
    }
    return out


# ─── Generation (per day / per project) ───────────────────────────────

def lesson_for_day(sb, sprint, day_row, project):
    """Generate the day's Watch · Lesson content (LLM → deterministic fallback).

    Returns a dict {"title", "script", "key_points"} ready to store in
    sprint_days.action_payload.lesson.
    """
    job = _top_job(sb, sprint.get("cluster_key"))
    project_title = (project or {}).get("title") or day_row.get("title") or ""
    fallback = _fallback_lesson(job, day_row.get("day_no"), day_row.get("action_type"), project_title)
    try:
        text = call_llm(_lesson_prompt(job, day_row.get("day_no"), day_row.get("action_type"), project_title), timeout=15)
        parsed = _parse_json(text)
    except Exception:
        parsed = None
    if not parsed or not parsed.get("script"):
        return fallback
    return {
        "title": parsed["title"] or fallback["title"],
        "script": parsed["script"],
        "key_points": parsed["key_points"] or fallback["key_points"],
    }


def project_anatomy(sb, sprint, project_index):
    """Generate one copy-work project's clone_steps + rubric (LLM → fallback)."""
    job = _top_job(sb, sprint.get("cluster_key"))
    fallback = _project_fallback(job, project_index)
    try:
        text = call_llm(_project_prompt(job, project_index), timeout=15)
        parsed = _parse_project(text, fallback)
    except Exception:
        parsed = fallback
    return parsed


# ─── The async worker ─────────────────────────────────────────────────

def generate_sprint_content(sb, sprint_id):
    """Fill every day's lesson payload + every project's anatomy for a sprint.

    Runs on a background thread (routes/main.py start_sprint). Each day/project
    is written to the DB as it completes — the populated-payload count is the
    progress the frontend polls. Idempotent: only fills empty payloads.
    """
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
        new_payload["lesson"] = lesson
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


def generation_progress(sb, sprint_id):
    """(generated, total) — count of days whose lesson payload is populated."""
    days = sb.table("sprint_days").select("action_payload").eq("sprint_id", sprint_id).execute().data
    total = len(days) or 14
    generated = sum(1 for d in days if (d.get("action_payload") or {}).get("lesson"))
    return generated, total
