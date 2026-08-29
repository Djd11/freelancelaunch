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

# Quiz + answer-key fields appended to every lesson prompt (content-quality
# P1-3): a 3-4 question knowledge check with a parallel, specific answer key.
# Stored inside sprint_days.action_payload.lesson (JSONB — no migration).
_QUIZ_INSTRUCTION = (
    ' Also include a "quiz": a list of 3-4 short knowledge-check questions '
    '(strings) that test the learner on the EXACT trigger / variable / block / '
    'step just taught (not generic trivia), and a parallel "quiz_answers": '
    'list of 3-4 answer strings (one per question) that are specific and '
    'non-generic — each answer must name the concrete feature/syntax from the '
    'lesson. Keep "quiz" and "quiz_answers" the same length.'
)

# Engagement fields (pre-lesson hook/overview/usefulness/pre-quiz) appended to
# every lesson prompt so the Day View can render an engaging preview. Optional
# in output; the template degrades gracefully when any are missing.
_ENGAGEMENT_INSTRUCTION = (
    ' Also include these four OPTIONAL engagement fields so the day preview is '
    'compelling: (1) "hook": a 1-2 sentence punchy opener that names the '
    "learner's concrete freelance win for THIS niche (e.g. \"Land your first "
    'Klaviyo automation gig faster\"); (2) "day_overview": a list of 2-4 short '
    'strings, "what you will learn today"; (3) "usefulness_context": 1 paragraph '
    'explaining WHY this skill helps win freelance jobs, citing the live job '
    'posting above (name the specific tool/feature clients ask for); (4) '
    '"pre_quiz": a list of 1-2 objects testing the learner\'s PRIOR intuition '
    'BEFORE the lesson — each object MUST be {"q": "...", "options": '
    '["...","..."], "answer": <0-based index into options>}. Keep "pre_quiz" '
    'distinct from the post-lesson "quiz". Write "script" as a NARRATIVE ARC '
    '(context -> action -> payoff), still >80 chars, still ending with '
    '"key_points" + "pitfalls".'
)


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
            '"key_points": ["...", "..."], "pitfalls": ["...", "..."], "quiz": ["...", "..."], '
            '"quiz_answers": ["...", "..."], "hook": "...", "day_overview": ["...","..."], "usefulness_context": "...", "pre_quiz": [{"q":"...","options":["...","..."],"answer":0}]}.'
        )
        return prompt + _QUIZ_INSTRUCTION + _ENGAGEMENT_INSTRUCTION

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
            '"key_points": ["...", "..."], "pitfalls": ["...", "..."], "quiz": ["...", "..."], '
            '"quiz_answers": ["...", "..."], "hook": "...", "day_overview": ["...","..."], "usefulness_context": "...", "pre_quiz": [{"q":"...","options":["...","..."],"answer":0}]}.'
        )
        if gap_fill_topic:
            prompt += f" Gap-fill focus: {gap_fill_topic}."
        return prompt + _QUIZ_INSTRUCTION + _ENGAGEMENT_INSTRUCTION

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
            '"key_points": ["...", "..."], "pitfalls": ["...", "..."], "quiz": ["...", "..."], '
            '"quiz_answers": ["...", "..."], "hook": "...", "day_overview": ["...","..."], "usefulness_context": "...", "pre_quiz": [{"q":"...","options":["...","..."],"answer":0}]}.'
        )
        return prompt + _QUIZ_INSTRUCTION + _ENGAGEMENT_INSTRUCTION

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
            '"key_points": ["...", "..."], "pitfalls": ["...", "..."], "quiz": ["...", "..."], '
            '"quiz_answers": ["...", "..."], "hook": "...", "day_overview": ["...","..."], "usefulness_context": "...", "pre_quiz": [{"q":"...","options":["...","..."],"answer":0}]}.'
        )
        return prompt + _QUIZ_INSTRUCTION + _ENGAGEMENT_INSTRUCTION

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
        '"key_points": ["...", "..."], "pitfalls": ["...", "..."], "quiz": ["...", "..."], '
        '"quiz_answers": ["...", "..."], "hook": "...", "day_overview": ["...","..."], "usefulness_context": "...", "pre_quiz": [{"q":"...","options":["...","..."],"answer":0}]}.'
    )
    return prompt + _QUIZ_INSTRUCTION + _ENGAGEMENT_INSTRUCTION


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


def _normalize_engagement(data):
    """Normalize the four engagement preview fields from a raw lesson dict.

    Shared by both `_parse_json` (fresh LLM output) and `clean_lesson`
    (backfilled rows) so freshly generated and already-stored lessons are
    consistent. `pre_quiz` items whose `answer` is not a valid 0-based index
    into `options` are DROPPED (models frequently emit 1-based or out-of-range
    indices — an unclamped index would yield an empty reveal or IndexError).
    """
    raw_pq = (data.get("pre_quiz")) or []
    norm_pq = []
    for it in raw_pq:
        if not isinstance(it, dict):
            continue
        q = str(it.get("q") or it.get("question") or "").strip()
        opts = [str(o).strip() for o in (it.get("options") or []) if str(o).strip()]
        try:
            ans = int(it.get("answer") if it.get("answer") is not None else it.get("answer_index"))
        except (ValueError, TypeError):
            ans = -1
        if not q or len(opts) < 2:
            continue                      # needs a real question + >=2 options
        if not (0 <= ans < len(opts)):
            continue                      # DROP unsafe/out-of-range answer index
        norm_pq.append({"q": q, "options": opts, "answer": ans})
    return {
        "hook": _clean_escapes(str(data.get("hook") or "")).strip(),
        "day_overview": [_clean_escapes(str(x)) for x in (data.get("day_overview") or []) if str(x).strip()],
        "usefulness_context": _clean_escapes(str(data.get("usefulness_context") or "")).strip(),
        "pre_quiz": norm_pq,
    }


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
        "quiz": [_clean_escapes(q) for q in (lesson.get("quiz") or [])],
        "quiz_answers": [_clean_escapes(a) for a in (lesson.get("quiz_answers") or [])],
    }
    eng = _normalize_engagement(lesson)
    clean["hook"] = eng["hook"]
    clean["day_overview"] = eng["day_overview"]
    clean["usefulness_context"] = eng["usefulness_context"]
    clean["pre_quiz"] = eng["pre_quiz"]
    if lesson.get("voiceover"):
        clean["voiceover"] = lesson["voiceover"]
    return clean


def _parse_json(text):
    """Lesson-shape parser — title/script/key_points/quiz from the raw LLM dict."""
    data = _load_json_object(text)
    if not data:
        return None
    eng = _normalize_engagement(data)
    return {
        "title": _clean_escapes(str(data.get("title") or "")).strip(),
        "objective": _clean_escapes(str(data.get("objective") or "")).strip(),
        "script": _clean_escapes(str(data.get("script") or "")).strip(),
        "key_points": [_clean_escapes(str(k)) for k in (data.get("key_points") or []) if str(k).strip()],
        "pitfalls": [_clean_escapes(str(p)) for p in (data.get("pitfalls") or []) if str(p).strip()],
        "quiz": [_clean_escapes(str(q)) for q in (data.get("quiz") or []) if str(q).strip()],
        "quiz_answers": [_clean_escapes(str(a)) for a in (data.get("quiz_answers") or []) if str(a).strip()],
        "hook": eng["hook"],
        "day_overview": eng["day_overview"],
        "usefulness_context": eng["usefulness_context"],
        "pre_quiz": eng["pre_quiz"],
    }


def _quiz_verify_prompt(lesson):
    """Build the verification prompt for a generated quiz (content-quality P1-3):
    mirrors daily-tech-study's practice discipline — the answers must be specific
    and non-generic, or they get repaired."""
    import json as _json
    return (
        "You are a rigorous technical editor. A lesson was generated with a quiz "
        "and answer key. Verify each answer is SPECIFIC (names the exact feature, "
        "trigger, variable, or syntax from the lesson) and non-generic. "
        "If every answer is specific, reply exactly: {\"ok\": true}. "
        "If any answer is generic or wrong, reply with a REPAIRED JSON: "
        '{"quiz": ["...", "..."], "quiz_answers": ["specific answer", "..."]} '
        "matching the lesson below.\n\n"
        "LESSON:\n" + _json.dumps(lesson, ensure_ascii=False)
    )


def _verify_lesson_quiz(sb, lesson):
    """Run/repair verification for the lesson's quiz (content-quality P1-3).

    Returns (quiz, quiz_answers) — either the original pair (when the LLM
    confirms they are specific) or a repaired pair. A None/garbage LLM response
    keeps the original answers (best-effort, never drops the quiz)."""
    quiz = lesson.get("quiz") or []
    answers = lesson.get("quiz_answers") or []
    if not quiz or not answers:
        return quiz, answers
    try:
        text = call_llm(_quiz_verify_prompt(lesson), timeout=60, max_retries=2, backoff_base=2)
    except Exception:
        return quiz, answers
    if not text:
        return quiz, answers
    data = _load_json_object(text)
    if not data:
        return quiz, answers
    if data.get("ok") is True:
        return quiz, answers
    new_quiz = [str(q) for q in (data.get("quiz") or []) if str(q).strip()]
    new_answers = [str(a) for a in (data.get("quiz_answers") or []) if str(a).strip()]
    if new_quiz and new_answers and len(new_quiz) == len(new_answers):
        return new_quiz, new_answers
    return quiz, answers


def quiz_from_lesson_prompt(lesson):
    """DEDICATED generation prompt for backfilling a quiz onto an EXISTING
    lesson (content-quality P1-1 / F3). Takes the lesson's title/script/
    key_points/pitfalls and asks the model for 3-4 knowledge-check questions
    with a parallel, specific answer key.

    This is intentionally NOT `_quiz_verify_prompt`: that prompt is a verify/
    repair prompt ("A lesson was generated WITH a quiz…") and `_verify_lesson_quiz`
    early-returns when the input has no quiz — so feeding a quiz-less lesson
    through it is a silent no-op. Backfill needs a generation prompt that
    CREATES the quiz from nothing.
    """
    lesson_blob = json.dumps({
        "title": lesson.get("title") or "",
        "script": lesson.get("script") or "",
        "key_points": lesson.get("key_points") or [],
        "pitfalls": lesson.get("pitfalls") or [],
    }, ensure_ascii=False)
    return (
        "You are writing a knowledge-check quiz for an EXISTING lesson that was "
        "already generated. Read the lesson below and write a short quiz that "
        "tests the learner on the EXACT trigger / variable / block / step taught "
        "in it (not generic trivia). "
        'Reply with JSON only: {"quiz": ["...", "...", "..."], '
        '"quiz_answers": ["specific answer", "...", "..."]} where "quiz" is a '
        'list of 3-4 short knowledge-check questions (strings) and "quiz_answers" '
        "is a parallel list of 3-4 answer strings (one per question) that are "
        "specific and non-generic — each answer must name the concrete "
        "feature/syntax from the lesson. Keep \"quiz\" and \"quiz_answers\" the "
        "same length.\n\n"
        "LESSON:\n" + lesson_blob
    )


def backfill_quiz(sb, sprint_id):
    """Backfill `quiz`/`quiz_answers` for a sprint's legacy lessons that lack a
    valid quiz (data-era gap: pre-feature lessons were generated before the quiz
    field existed, and `generate_sprint_content` skips already-generated days).

    - REQUIRES `sprint_id` (no tenant-wide default) — runs on one sprint only
      (P1-1 / F2: avoids over-reaching other tenants' data).
    - Selects days whose lesson EXISTS and `needs_quiz = not (quiz and
      quiz_answers and len(quiz) == len(quiz_answers))`, so it also repairs
      malformed lessons (quiz present but answers missing / length-mismatched).
    - Days with no lesson are skipped (F5): backfill only repairs existing
      lessons.
    - For each selected day: generate via `quiz_from_lesson_prompt`, parse, then
      run the existing `_verify_lesson_quiz` repair/parity pass, and merge
      quiz/quiz_answers into `action_payload.lesson` ONLY when the generated quiz
      is non-empty and length-matched (Fix 2 guard). Idempotent: a satisfied day
      is skipped, so a re-run resumes safely.
    Returns the number of days actually updated.
    """
    days = sb.table("sprint_days").select("day_no,action_payload") \
        .eq("sprint_id", sprint_id).order("day_no").execute().data
    updated = 0
    for d in days:
        day_no = d.get("day_no")
        payload = dict(d.get("action_payload") or {})
        lesson = payload.get("lesson")
        if not lesson:
            continue  # F5: no lesson to backfill
        quiz = lesson.get("quiz") or []
        answers = lesson.get("quiz_answers") or []
        if quiz and answers and len(quiz) == len(answers):
            continue  # already valid — idempotent skip
        text = call_llm(quiz_from_lesson_prompt(lesson), timeout=90, max_retries=3, backoff_base=2)
        if not text:
            continue
        parsed = _parse_json(text)
        if not parsed:
            continue
        parsed_quiz = parsed.get("quiz") or []
        parsed_answers = parsed.get("quiz_answers") or []
        if not parsed_quiz or not parsed_answers:
            continue
        # verify/repair pass (enforces specificity + length parity)
        new_quiz, new_answers = _verify_lesson_quiz(sb, {
            "quiz": parsed_quiz, "quiz_answers": parsed_answers,
        })
        # Fix 2 guard: only merge when non-empty + length-matched
        if not new_quiz or not new_answers or len(new_quiz) != len(new_answers):
            continue
        lesson["quiz"] = new_quiz
        lesson["quiz_answers"] = new_answers
        payload["lesson"] = lesson
        sb.table("sprint_days").update({"action_payload": payload}) \
            .eq("sprint_id", sprint_id).eq("day_no", day_no).execute()
        updated += 1
    return updated


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
    quiz, quiz_answers = _verify_lesson_quiz(sb, parsed)
    return {
        "title": parsed["title"],
        "objective": parsed["objective"] or "",
        "script": parsed["script"],
        "key_points": parsed["key_points"] or [],
        "pitfalls": parsed["pitfalls"] or [],
        "quiz": quiz,
        "quiz_answers": quiz_answers,
        "hook": parsed.get("hook") or "",
        "day_overview": parsed.get("day_overview") or [],
        "usefulness_context": parsed.get("usefulness_context") or "",
        "pre_quiz": parsed.get("pre_quiz") or [],
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
