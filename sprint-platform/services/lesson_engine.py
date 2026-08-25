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
from routes import DAY_TO_PROJECT


def _excerpt(text, limit=1500):
    """Job-posting head for prompts. ~1500 chars carries requirements, stack
    and client language — keyword-level grounding (~220) let the model fill
    the void with generic boilerplate (content-quality P1-1)."""
    if not text:
        return ""
    text = " ".join((text or "").split())
    return text[:limit].rstrip() + ("…" if len(text) > limit else "")


def _top_job(sb, cluster_key, project_index=None, rotate=None):
    """Active postings in the cluster (same pick as mock_contract_engine).

    Relevance filter: when possible, prefer jobs whose title matches the
    cluster's keywords (e.g. email-automation → jobs with 'email', 'klaviyo',
    'cart'). Generic RSS feeds may land unrelated jobs in a cluster; this
    ensures the LLM generates content about the right domain.

    Deterministic rotation (content-quality P1-2 — never regenerate every day
    from feed[0]):
    - project_index given (copy-work days): feed[(project_index - 1) % len],
      so each of the 3 projects draws distinct material even on thin feeds;
    - otherwise rotate=day_no: feed[(day_no - 1) % len], so Phase B/C days
      cycle across the ranked feed instead of repeating one posting.
    """
    feed = sb.table("job_feed").select("*") \
        .eq("cluster_key", cluster_key).eq("status", "active") \
        .order("unlock_day").order("id").execute().data
    if not feed:
        return None

    # Fetch cluster keywords for relevance scoring
    cluster_row = sb.table("job_clusters").select("keywords") \
        .eq("cluster_key", cluster_key).limit(1).execute().data
    keywords = [k.lower() for k in ((cluster_row[0].get("keywords") or []) if cluster_row else [])]

    if keywords:
        # Rank jobs: title contains cluster keyword → higher priority
        def _relevance(job):
            title_lower = (job.get("title") or "").lower()
            # Manual-sourced jobs are usually the most relevant
            manual_boost = 0 if job.get("source_platform") == "manual" else -1
            kw_hits = sum(1 for kw in keywords if kw in title_lower)
            return (manual_boost, kw_hits)
        feed = sorted(feed, key=_relevance, reverse=True)

    n = len(feed)
    if project_index is not None and int(project_index) >= 1:
        return feed[(int(project_index) - 1) % n]
    if rotate is not None:
        try:
            offset = max(int(rotate), 1) - 1
        except (TypeError, ValueError):
            offset = 0
        return feed[offset % n]
    return feed[0]


def _domain_tools(sb, cluster_key, job=None):
    """Tool vocabulary derived ONLY from the cluster's keywords and the top
    posting's skills (content-quality P0-1: prompts must never hard-code
    platform names — a web-scraping learner must never be taught Klaviyo).
    The posting description itself flows into every prompt via _excerpt."""
    tools = []

    def _add(value):
        name = str(value or "").strip()
        if name and name.lower() not in {t.lower() for t in tools}:
            tools.append(name)

    rows = sb.table("job_clusters").select("keywords") \
        .eq("cluster_key", cluster_key).limit(1).execute().data
    for kw in ((rows[0].get("keywords") if rows else None) or []):
        _add(kw)
    skills = (job or {}).get("skills")
    if isinstance(skills, list):
        for sk in skills:
            _add(sk)
    return tools[:10]


def _domain_context(tools):
    """The 'use ONLY these tools' block injected into every prompt branch."""
    names = ", ".join(tools) if tools else \
        "exactly the tools named in the job posting"
    return (
        f"This niche's toolset: {names}. Reference ONLY these tools/platforms "
        "and their actual feature names — never mention tools from an "
        "unrelated niche."
    )


# ─── LLM prompt + parsing ─────────────────────────────────────────────

def _lesson_prompt(job, day, action_type, project_title,
                   gap_fill_topic=None, domain_context=""):
    job_title = (job or {}).get("title") or "the target job"
    excerpt = _excerpt((job or {}).get("description") or "")
    ctx = f"{domain_context} " if domain_context else ""

    # Day 1 (setup): orientation lesson — what the sprint is about, tools needed,
    # what the learner will build across the 14 days. NOT a copy-work task.
    if action_type == "setup":
        prompt = (
            "You write an orientation lesson for Day 1 of a 14-day freelancer sprint. "
            f"The sprint is for: \"{job_title}\". "
            f"The job posting says: \"{excerpt}\". {ctx}"
            "Write a lesson that covers: (1) what the learner will build by the end of "
            "the sprint, (2) the tools/platforms they need from this niche's toolset, "
            "(3) what copy-work means and how the 14 days are structured (Phase A: "
            "copy-work replication, Phase B: mock contract, Phase C: proposals), "
            "(4) one quick win they can do today to get started. "
            'Reply with JSON only: {"title": "...", "objective": "...", "script": "...", '
            '"key_points": ["...", "..."], "pitfalls": ["...", "..."]}.'
        )
        return prompt

    # Copy-work days (2-5): step-by-step build instructions
    if action_type == "copywork":
        prompt = (
            "You write a step-by-step build lesson for a freelancer sprint. "
            f"The job title is: \"{job_title}\". "
            f"The job posting says: \"{excerpt}\". {ctx}"
            f"Day {day}, Project: {project_title}. "
            "Write a lesson that teaches the learner to rebuild this exact flow. "
            "The script MUST include: (1) the specific trigger to configure in one "
            "of the niche's tools, (2) the exact blocks/steps to add in order, "
            "(3) the exact variable/dynamic-content syntax of that tool, "
            "(4) how to test it before going live. "
            "Be concrete and actionable — the learner should be able to follow along "
            "click-by-click using this toolset's actual feature names. "
            'Reply with JSON only: {"title": "...", "objective": "...", "script": "...", '
            '"key_points": ["...", "..."], "pitfalls": ["...", "..."]}.'
        )
        if gap_fill_topic:
            prompt += f" Gap-fill focus: {gap_fill_topic}."
        return prompt

    # Contract days (6-8): executing the mock contract
    if action_type == "contract":
        prompt = (
            "You write a lesson for executing a mock client contract in a freelancer sprint. "
            f"The job title is: \"{job_title}\". "
            f"The job posting says: \"{excerpt}\". {ctx}"
            f"Day {day}, working on the mock contract deliverable. "
            "Write a lesson that teaches the learner to execute the contract step by step: "
            "what to build, how to structure the deliverable, what documentation to write. "
            "Be concrete — reference specific features and integrations of this niche's "
            "tools, and deliverable formats the client would expect. "
            'Reply with JSON only: {"title": "...", "objective": "...", "script": "...", '
            '"key_points": ["...", "..."], "pitfalls": ["...", "..."]}.'
        )
        return prompt

    # Case-study days (9-10): writing the case study
    if action_type == "case-study":
        prompt = (
            "You write a lesson for writing a professional case study in a freelancer sprint. "
            f"The job title is: \"{job_title}\". "
            f"The job posting says: \"{excerpt}\". {ctx}"
            f"Day {day}, the learner writes their Problem / Solution / Result case study. "
            "Write a lesson that teaches: (1) how to frame the client's problem using "
            "the job posting's terminology, (2) how to describe the solution they built, "
            "(3) how to quantify results (even estimated ones), (4) the structure that "
            "clients want to see. This case study becomes their portfolio piece. "
            'Reply with JSON only: {"title": "...", "objective": "...", "script": "...", '
            '"key_points": ["...", "..."], "pitfalls": ["...", "..."]}.'
        )
        return prompt

    # Proposal days (11-14): building and sending proposals
    prompt = (
        "You write a lesson for sending proposals to live job postings in a freelancer sprint. "
        f"The job title is: \"{job_title}\". "
        f"The job posting says: \"{excerpt}\". {ctx}"
        f"Day {day}, the learner sends proposals to real clients. "
        "Write a lesson that teaches: (1) how to write an opening hook that references "
        "the job posting's specific needs, (2) how to include proof from their mock "
        "contract and case study, (3) how to personalize each proposal, (4) what to "
        "do after sending (track, follow up). "
        'Reply with JSON only: {"title": "...", "objective": "...", "script": "...", '
        '"key_points": ["...", "..."], "pitfalls": ["...", "..."]}.'
    )
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


def _clean_escapes(value):
    """Undo double-escaped LLM JSON string fields.

    The model sometimes writes literal ``\\n``/``\\t`` characters inside the
    JSON string values instead of real control characters. ``json.loads``
    keeps those literal backslashes, so a script arrives as one flat string
    of ``\\n`` sequences and renders as raw text. Normalize them to real
    newlines/tabs so ``format_script`` can split on line breaks.
    """
    if not isinstance(value, str):
        return value
    return value.replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t")


def clean_lesson(lesson):
    """Return a copy of a generated lesson with literal escape sequences
    normalized. New content is already clean (``_parse_json`` normalizes);
    this heals already-stored rows so the day view's readable text AND the
    two-panel player props never show raw ``\\n``."""
    if not lesson:
        return lesson
    clean = {
        "title": _clean_escapes(lesson.get("title")),
        "objective": _clean_escapes(lesson.get("objective")),
        "script": _clean_escapes(lesson.get("script")),
        "key_points": [_clean_escapes(k) for k in (lesson.get("key_points") or [])],
        "pitfalls": [_clean_escapes(p) for p in (lesson.get("pitfalls") or [])],
    }
    if lesson.get("voiceover"):
        clean["voiceover"] = lesson["voiceover"]
    return clean


def _parse_json(text):
    """Lesson-shape parser — title/script/key_points from the raw LLM dict."""
    data = _load_json_object(text)
    if not data:
        return None
    return {
        "title": _clean_escapes(str(data.get("title") or "")).strip(),
        "objective": _clean_escapes(str(data.get("objective") or "")).strip(),
        "script": _clean_escapes(str(data.get("script") or "")).strip(),
        "key_points": [_clean_escapes(str(k)) for k in (data.get("key_points") or []) if str(k).strip()],
        "pitfalls": [_clean_escapes(str(p)) for p in (data.get("pitfalls") or []) if str(p).strip()],
    }


def _project_prompt(job, project_index, domain_context=""):
    job_title = (job or {}).get("title") or "the target job"
    excerpt = _excerpt((job or {}).get("description") or "")
    ctx = f"{domain_context} " if domain_context else ""
    # Different project types for variety across the 3 copy-work projects
    project_focus = {
        1: "the core flow (e.g. welcome/onboarding series, main automation)",
        2: "the recovery flow (e.g. abandoned cart, winback)",
        3: "the post-purchase flow (e.g. upsell, review request)",
    }
    focus = project_focus.get(project_index, "the main automation")
    return (
        "You design a copy-work replication task for a freelancer sprint. "
        f"The job title is: \"{job_title}\". "
        f"The job posting says: \"{excerpt}\". {ctx}"
        f"Design replication project {project_index} of 3: {focus}. "
        "The clone_steps must be specific actions the learner takes in this "
        "niche's tools (e.g. 'Create the automation with the start event named "
        "in the posting', 'Add the message step with the dynamic content block', "
        "'Set the delay to 30 minutes'). "
        "Each step must name the exact feature, trigger, or variable to use. "
        "The rubric must be auto-checkable pass/fail criteria about observable "
        "artifacts (e.g. 'Flow triggers on the posting's start event', 'Message "
        "contains the dynamic summary block', 'Follow-up message is scheduled'). "
        "Also include \"reference_spec\": a screen-by-screen breakdown of the "
        "finished reference build the learner replicates — each screen, its key "
        "settings, and sample copy/subject lines. This is the artifact learners "
        "copy from, so it must be complete without any external link. "
        'Reply with JSON only: {"title": "...", "clone_steps": ["...", "..."], '
        '"rubric": ["...", "...", "..."], "reference_spec": "...", '
        '"gap_fill_topic": "..." or null}. '
        "clone_steps = 4-5 concrete build steps; rubric = 3 acceptance criteria."
    )


def _parse_project(text):
    """Project-anatomy parser — the raw LLM dict keeps clone_steps/rubric/
    reference_spec (the lesson-shape _parse_json would drop them)."""
    data = _load_json_object(text)
    if not data or not data.get("title"):
        raise LLMGenerationError("LLM returned unparseable project anatomy")
    return {
        "title": _clean_escapes(str(data.get("title") or "")).strip(),
        "clone_steps": [_clean_escapes(str(s)) for s in (data.get("clone_steps") or []) if str(s).strip()],
        "rubric": [_clean_escapes(str(r)) for r in (data.get("rubric") or []) if str(r).strip()],
        "reference_spec": _clean_escapes(str(data.get("reference_spec") or "")).strip(),
        "gap_fill_topic": _clean_escapes(data.get("gap_fill_topic")),
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
    project_index = (project or {}).get("project_index")
    day_no = day_row.get("day_no")
    job = _top_job(sb, sprint.get("cluster_key"), project_index, rotate=day_no)
    if day_no == 5 and not gap_fill_topic:
        gap_fill_topic = _gap_fill_topic(sb, sprint.get("id"))
    project_title = (project or {}).get("title") or day_row.get("title") or ""
    prompt = _lesson_prompt(
        job, day_no, day_row.get("action_type"), project_title,
        gap_fill_topic=gap_fill_topic,
        domain_context=_domain_context(_domain_tools(sb, sprint.get("cluster_key"), job)),
    )
    text = call_llm(prompt, timeout=90, max_retries=3, backoff_base=2)
    if not text:
        raise LLMGenerationError("No LLM provider answered for the day's lesson")
    parsed = _parse_json(text)
    if not parsed or not parsed.get("script"):
        raise LLMGenerationError("LLM returned an unusable lesson (missing script)")
    return {
        "title": parsed["title"],
        "objective": parsed["objective"] or "",
        "script": parsed["script"],
        "key_points": parsed["key_points"] or [],
        "pitfalls": parsed["pitfalls"] or [],
    }


def project_anatomy(sb, sprint, project_index):
    """Generate one copy-work project's clone_steps + rubric + reference build
    spec (LLM-only)."""
    job = _top_job(sb, sprint.get("cluster_key"), project_index)
    prompt = _project_prompt(
        job, project_index,
        domain_context=_domain_context(_domain_tools(sb, sprint.get("cluster_key"), job)),
    )
    text = call_llm(prompt, timeout=90, max_retries=3, backoff_base=2)
    if not text:
        raise LLMGenerationError("No LLM provider answered for the project anatomy")
    return _parse_project(text)


def _store_reference_spec(sb, sprint_id, project_index, spec):
    """Persist a generated reference build spec so the day view shows WHAT to
    replicate without any external link (content-quality P0-2 — seeded
    example.com placeholders are gone).

    Primary home is the project row's `reference_spec` column (apply
    db/migrations/003_copywork_reference_spec.sql). Until that migration has
    run in a given environment, fall back to storing it on each mapped
    copy-work day's action_payload so the feature works with zero schema
    change; the day view reads both.
    """
    mapped_days = sorted(d for d, p in DAY_TO_PROJECT.items() if p == project_index)
    try:
        sb.table("copywork_projects").update({"reference_spec": spec}) \
            .eq("sprint_id", sprint_id).eq("project_index", project_index).execute()
    except Exception:
        pass  # column not migrated yet — payload fallback below carries it
    for day_no in mapped_days:
        rows = sb.table("sprint_days").select("day_no,action_payload") \
            .eq("sprint_id", sprint_id).eq("day_no", day_no).limit(1).execute().data
        if not rows:
            continue
        payload = dict(rows[0].get("action_payload") or {})
        payload["reference_spec"] = spec
        sb.table("sprint_days").update({"action_payload": payload}) \
            .eq("sprint_id", sprint_id).eq("day_no", day_no).execute()


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
            try:
                lesson = lesson_for_day(sb, sprint, day_row, project)
            except Exception as exc:
                # Stamp error on this day but continue to next day
                try:
                    err_payload = dict(payload)
                    err_payload["generation_error"] = f"Generation failed: {exc}"
                    sb.table("sprint_days").update({"action_payload": err_payload}) \
                        .eq("sprint_id", sprint_id).eq("day_no", day_row["day_no"]).execute()
                except Exception:
                    pass  # DB also down — just skip this day
                import logging
                logging.getLogger(__name__).warning("Day %d generation failed: %s", day_row.get("day_no"), exc)
                continue
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
            try:
                sb.table("sprint_days").update({"action_payload": new_payload}) \
                    .eq("sprint_id", sprint_id).eq("day_no", day_row["day_no"]).execute()
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("Day %d DB write failed: %s (will retry next round)", day_row.get("day_no"), exc)

        for index in (1, 2, 3):
            existing = sb.table("copywork_projects").select("id,clone_steps,title") \
                .eq("sprint_id", sprint_id).eq("project_index", index).limit(1).execute().data
            if not existing:
                continue
            row = existing[0]
            if row.get("clone_steps"):
                continue  # anatomy already generated
            # Retry logic: try up to 3 times for each project anatomy.
            # A single failure must not stop the other projects from generating.
            for attempt in range(3):
                try:
                    anatomy = project_anatomy(sb, sprint, index)
                    if anatomy.get("clone_steps") and anatomy.get("rubric"):
                        # P1-4: an LLM answer without a gap-fill topic must
                        # never null an existing flagged focus — only write
                        # the field when the model actually supplied one.
                        update_fields = {
                            "title": anatomy["title"],
                            "clone_steps": anatomy["clone_steps"],
                            "rubric": anatomy["rubric"],
                        }
                        if anatomy.get("gap_fill_topic"):
                            update_fields["gap_fill_topic"] = anatomy["gap_fill_topic"]
                        sb.table("copywork_projects").update(update_fields) \
                            .eq("sprint_id", sprint_id).eq("project_index", index).execute()
                        spec = anatomy.get("reference_spec")
                        if spec:
                            _store_reference_spec(sb, sprint_id, index, spec)
                        break  # success, move to next project
                except (LLMGenerationError, Exception) as exc:
                    if attempt == 2:
                        # All retries failed — log but don't crash the worker.
                        # The UI shows "Project anatomy is being generated…"
                        # and a retry will heal it.
                        import logging
                        logging.getLogger(__name__).warning(
                            "project anatomy failed for %s project %d: %s", sprint_id, index, exc)
    except LLMGenerationError as exc:
        # LLM-only: never substitute templates — record the failure so the UI
        # surfaces it. Don't re-raise: individual day failures are already
        # stamped inside the loop, so the worker should continue with remaining days.
        import logging
        logging.getLogger(__name__).warning("Sprint content generation error for %s: %s", sprint_id, exc)

# ── Active generation tracking ──────────────────────────────────────────
# In-memory set of sprint IDs currently being generated by a background thread.
# Single-process Flask dev server: this is reliable. For multi-process deploys,
# replace with Redis set or DB flag.
_active_generations: set = set()


def start_generation(sprint_id: str) -> None:
    """Mark sprint as actively generating (background thread started)."""
    _active_generations.add(sprint_id)


def stop_generation(sprint_id: str) -> None:
    """Mark sprint as no longer actively generating (thread finished)."""
    _active_generations.discard(sprint_id)


def is_generating(sprint_id: str) -> bool:
    """True if a background thread is currently generating content for this sprint."""
    return sprint_id in _active_generations


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


def day_status_map(sb, sprint_id):
    """Return {day_no: 'ok'|'error'|'pending'} for every sprint day.

    Used by the dashboard to render a per-day content status track so the
    user can see at a glance which days have lessons and which failed.
    """
    days = sb.table("sprint_days").select("day_no,action_payload") \
        .eq("sprint_id", sprint_id).order("day_no").execute().data
    result = {}
    for d in days:
        day_no = d.get("day_no")
        payload = d.get("action_payload") or {}
        if payload.get("generation_error"):
            result[day_no] = "error"
        elif payload.get("lesson"):
            result[day_no] = "ok"
        else:
            result[day_no] = "pending"
    return result


def content_day_cards(day_rows):
    """Per-day dicts powering the dashboard's server-rendered Sprint Content
    grid. Status mirrors day_status_map: 'error' (payload carries a
    generation_error), 'ok' (lesson present), else 'pending'."""
    cards = []
    for d in day_rows:
        payload = d.get("action_payload") or {}
        lesson = payload.get("lesson") or {}
        if payload.get("generation_error"):
            status = "error"
        elif lesson:
            status = "ok"
        else:
            status = "pending"
        cards.append({
            "day_no": d.get("day_no"),
            "action_type": d.get("action_type") or "",
            "is_done": bool(d.get("is_done")),
            "lesson_title": (lesson.get("title") or "").strip(),
            "status": status,
        })
    return cards
