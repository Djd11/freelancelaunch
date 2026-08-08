"""
Curriculum Generator — Learning Science-Based Algorithm
Implements 5-phase pipeline: Decomposition → Daily Generation → Quality Scoring → Adaptation → Refresh
"""
import json
import httpx
import logging
import re
from typing import Optional
from flask import current_app

logger = logging.getLogger(__name__)

# ─── PHASE 1: SKILL DECOMPOSITION ──────────────────────────

SKILL_DECOMPOSITION_PROMPT = """You are an expert curriculum designer optimizing ONE metric: the fastest path for a complete beginner to land their first paid "{topic}" freelance contract.

This is NOT a comprehensive course — it is a race. Identify the smallest set of skills a beginner MUST have to deliver ONE small paid project and earn a first review, then sequence them on a strict critical path. Prune everything that does not help land contract #1 within 30 days.

Requirements:
- Identify 4-6 core competencies that form the SPINE of selling "{topic}" as a service
- Rank strictly by dependency: each competency must unlock the next
- For each competency, define its "smallest sellable deliverable" — the artifact a client would actually pay $50-200 for
- Do NOT include: business fundamentals, passive income, scaling, or advanced theory that won't help land the first contract
- Map competencies to a 30-day arc with four gates:
  - Days 1-5 "Ship Artifact #1": learn just enough to produce the first sellable deliverable
  - Days 6-10 "Platform Live": create the profile/gig/portfolio that makes the learner findable (include platform-specific training for Upwork, Fiverr, and Contra)
  - Days 11-20 "First Order": proposals/buyer requests, deliver small, earn first review
  - Days 21-30 "Rate Raise": pricing up, repeatability, contract-readiness
- Each competency must have: a Bloom's taxonomy learning objective (Create/Apply), a concrete success metric, and a real-world application
- The curriculum must be achievable in 60-90 minutes per day
- Every single day must produce a tangible output

Output ONLY valid JSON (no markdown):
{{
  "skill": "{topic}",
  "smallest_sellable_deliverable": "the artifact a beginner can charge $50-200 for",
  "critical_path": [
    {{"competency": "...", "dependency_order": 1, "smallest_deliverable": "...", "gate": 1, "objective": "Create ...", "success_metric": "...", "real_world_application": "..."}}
  ],
  "weeks": [
    {{"week": 1, "theme": "Ship Artifact #1", "days": "1-5", "focus": "Minimum skill to produce the first sellable deliverable"}},
    {{"week": 2, "theme": "Platform Live", "days": "6-10", "focus": "Profiles, gigs, and portfolio that make you findable"}},
    {{"week": 3, "theme": "First Order", "days": "11-20", "focus": "Proposals, delivering small, earning your first review"}},
    {{"week": 4, "theme": "Rate Raise", "days": "21-30", "focus": "Pricing up, repeat clients, and contract-readiness"}}
  ]
}}"""


# ─── PHASE 2: DAILY LESSON GENERATION ───────────────────────

DAILY_LESSON_PROMPT = """You are designing Day {day} of a 30-day "land your first freelance contract" sprint for "{topic}".

ARC CONTEXT:
- Milestone: {stage_theme} (Days {stage_days} of the sprint)
- Today's focus: {focus}
- Learning objective: {objective}
- Learner progress: Day {day}/30
- Target platforms: {platforms_text}

The learner's ONLY goal is to land their first paid freelance contract as fast as possible. Every minute must advance that goal. Cut any content that does not move the learner toward a live, findable, sellable freelance offering.

Hard rules:
1. TODAY'S ARTIFACT: The PRACTICE section MUST produce one concrete, tangible artifact the learner could show a client or publish today — a script, file, page, case-study draft, gig-title list, proposal, or pricing table. Begin PRACTICE by naming the artifact, e.g. "Artifact: scrape_output.csv" or "Artifact: gig-title-options.md".
2. CLIENT LENS: Teach each concept as "what a client pays for", never as academic theory. Anchor every explanation in one real freelance buying scenario.
3. SPECIFICITY: Use concrete numbers, real tools, and named examples. No generic advice ("do research", "be consistent").
4. SHORTEST PATH: If a sub-topic will not help land contract #1 within 30 days, omit it. Depth over breadth.
5. PLATFORM CONTEXT: Where relevant, tie the artifact to the target platform(s) in {platforms_text} (e.g., "this gig title goes on your Fiverr gig", "this case study uses Contra's Problem→Approach→Result format").

Generate a complete lesson with EXACTLY these 6 sections. Each section must be labeled with its heading exactly as shown:

## HOOK
(2 min) One sentence connecting today to their goal of landing a client. Include one surprising fact. End with one driving question they'll answer today.
[Write 2-3 sentences]

## CONCEPT
(15-20 min) Teach ONE core concept. Use a real freelancing example. Include a metaphor or analogy. Answer "why does this matter for getting clients?"
[Write 3-5 paragraphs, each 3-4 sentences]

## PRACTICE
(20-25 min) One hands-on exercise that produces the named artifact. Include a template or framework. Slightly challenging but achievable.
[Write 3-5 steps with clear instructions]

## RETRIEVAL
(5 min) EXACTLY 3 reflection prompts that require writing/creating, NOT selecting. Format numbered list.
1. Write down the 3 most important things you learned today.
2. Explain the core concept to someone who knows nothing about it.
3. What's one thing you're still confused about?

## SPACED REVIEW
(5 min) Connect today's concept to previous learning. One quick application question that bridges old and new knowledge.
[Write 2-3 sentences with a specific question]

## PREVIEW
(1 min) One sentence teasing what's coming next to create anticipation.

Rules:
- Total lesson time: 45-60 minutes
- 8th grade reading level
- Every claim must be actionable
- Output ONLY the 6 sections with their headings, no extra commentary"""


# ─── PHASE 3: QUALITY SCORING ───────────────────────────────

QUALITY_SCORING_PROMPT = """You are a contract-readiness reviewer for a 30-day "land your first freelance contract" sprint.

Rate this lesson on 10 criteria (1-10 each). For each, provide a score and 1-sentence explanation.

Criteria:
1. Contract Progress: Does this lesson move the learner toward a live, findable, sellable offering (not just knowledge)?
2. Artifact: Does the practice produce one concrete, client-showable artifact today?
3. Relevance: Is every sentence relevant to landing the FIRST contract within 30 days?
4. Specificity: Are examples concrete with real numbers and tools (not generic advice)?
5. Platform Link: Does it connect to a real freelance platform (Fiverr/Upwork/Contra) where applicable?
6. Actionability: Can the learner DO something immediately after reading?
7. Cognitive Load: Is it teaching ONE concept, not multiple?
8. Client Lens: Is the concept taught as "what a client pays for", not academic theory?
9. Time Estimate: Is it realistic in 45-60 minutes?
10. Depth over Breadth: Does it go deep on a contract-critical skill instead of listing many?

OUTPUT FORMAT (valid JSON only):
{{
  "scores": {{
    "contract_progress": 8,
    "artifact": 7,
    ...
  }},
  "explanations": {{
    "contract_progress": "Moves the learner toward a live offering by...",
    ...
  }},
  "total": 82,
  "pass": true,
  "feedback": "Optional improvement suggestions if total < 75"
}}

LESSON TO REVIEW:
{lesson_text}"""


# ─── QUALITY GATE ────────────────────────────────────────────

# Patterns that indicate low-quality / fallback content
_GENERIC_TITLE_PATTERNS = [
    re.compile(r"Part\s*\d+", re.IGNORECASE),
    re.compile(r"^Day\s+\d+:\s+\w.+\s+—\s+Part\s+\d+$", re.IGNORECASE),
    re.compile(r"^Core Concepts$", re.IGNORECASE),
]
_GENERIC_DESCRIPTION_PATTERNS = [
    re.compile(r"^Learn key \w+ concepts with practical applications for freelance work\.?$", re.IGNORECASE),
    re.compile(r"^Today we explore a key \w+ concept\.", re.IGNORECASE),
]


def validate_curriculum(curriculum: list[dict]) -> dict:
    """Validate a generated curriculum before saving to DB.

    Returns:
        {
            "valid": bool,
            "errors": [str],       # human-readable reasons
            "warnings": [str],     # non-blocking concerns
            "stats": { ... }       # uniqueness counts
        }
    """
    errors = []
    warnings = []
    if not curriculum:
        return {"valid": False, "errors": ["Empty curriculum"], "warnings": [], "stats": {}}

    titles = [d.get("title", "") for d in curriculum]
    descriptions = [d.get("description", "") for d in curriculum]
    practice_tasks = [d.get("practice_task", d.get("practice", "")) for d in curriculum]

    # 1. Check for duplicate titles
    seen_titles = set()
    dup_titles = []
    for t in titles:
        if t in seen_titles:
            dup_titles.append(t)
        seen_titles.add(t)
    if dup_titles:
        errors.append(f"{len(dup_titles)} duplicate titles found")

    # 2. Check for generic "Part X" titles
    generic_count = sum(1 for t in titles if any(p.search(t) for p in _GENERIC_TITLE_PATTERNS))
    if generic_count > len(titles) * 0.3:
        errors.append(f"{generic_count}/{len(titles)} titles match generic 'Part N' pattern")

    # 3. Check for duplicate descriptions — any duplication is a quality failure
    unique_descs = len(set(d.strip() for d in descriptions if d.strip()))
    non_empty = len([d for d in descriptions if d.strip()])
    if unique_descs < non_empty:
        errors.append(f"Only {unique_descs}/{non_empty} unique descriptions")

    # 4. Check for generic/fallback descriptions
    fallback_desc_count = sum(1 for d in descriptions if any(p.search(d) for p in _GENERIC_DESCRIPTION_PATTERNS))
    if fallback_desc_count > len(descriptions) * 0.5:
        errors.append(f"{fallback_desc_count}/{len(descriptions)} descriptions match generic fallback pattern")

    # 5. Check for duplicate practice tasks
    unique_practice = len(set(p.strip() for p in practice_tasks if p.strip()))
    if unique_practice < 3 and len(practice_tasks) > 5:
        errors.append(f"Only {unique_practice} unique practice tasks across {len(practice_tasks)} days")

    # 6. Warnings for borderline cases
    if unique_descs < len(descriptions):
        warnings.append(f"{len(descriptions) - unique_descs} descriptions are non-unique")

    stats = {
        "total_days": len(curriculum),
        "unique_titles": len(seen_titles),
        "unique_descriptions": unique_descs,
        "unique_practice_tasks": unique_practice,
    }

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": stats,
    }


def is_fallback_content(lesson: dict) -> bool:
    """Check if a single lesson looks like fallback/generic content."""
    title = lesson.get("title", "")
    if any(p.search(title) for p in _GENERIC_TITLE_PATTERNS):
        return True
    desc = lesson.get("description", "")
    if any(p.search(desc) for p in _GENERIC_DESCRIPTION_PATTERNS):
        return True
    return False


# ─── CONTRACT-FIRST ARC (GATES) ─────────────────────────────
# The objective function: minimize time-to-first-contract. The 30-day
# curriculum is a race with four hard milestones, not four equal theme blocks.

GATES = [
    (1, 5, "Ship Artifact #1", "learn the minimum skill and produce your first sellable deliverable"),
    (6, 10, "Platform Live", "create profiles, gigs, and portfolio that make you findable"),
    (11, 20, "First Order", "send proposals, deliver a small project, earn your first review"),
    (21, 30, "Rate Raise", "price up, win repeat clients, and get contract-ready"),
]


def _gate_for_day(day: int) -> dict:
    """Return the contract-arc milestone containing a given day."""
    for start, end, name, desc in GATES:
        if start <= day <= end:
            return {"start": start, "end": end, "name": name, "desc": desc}
    start, end, name, desc = GATES[-1]
    return {"start": start, "end": end, "name": name, "desc": desc}


# Day-by-day focus for the contract-first arc. Platform days (see
# _PLATFORM_FULL_SLOTS / _PLATFORM_ACTIVATION_SLOTS below) replace the skill
# day at that slot, so entries here only apply to non-platform days.
_DAY_FOCUS = {
    # ── Gate 1: Ship Artifact #1 (Days 1-5) ──
    1: "Setup & First Working Output",
    2: "Core Concept — One Concept, One Mini Output",
    3: "First Practical Task — Deliverable #1 (Step 1)",
    4: "Tooling & Environment — Deliverable #1 (Step 2)",
    5: "Ship It! — Portfolio Artifact #1",
    # ── Gate 2: Platform Live (Days 6-10) ──
    6: "Define Your Freelance Offer & Niche",
    7: "Real-World Example — Mini Output",
    8: "Portfolio Case Study: Problem → Approach → Result",
    9: "Common Pitfalls — Mini Output",
    10: "Price Your First Gig",
    # ── Gate 3: First Order (Days 11-20) ──
    11: "Intermediate Techniques — Mini Output",
    12: "Advanced Concepts — Mini Output",
    13: "Workflow Optimization — Mini Output",
    14: "Draft Your First Proposal / Buyer Request",
    15: "Quality Standards — Mini Output",
    16: "Advanced Workflows — Mini Output",
    17: "Client-Style Project Simulation",
    18: "Portfolio Piece #2 — Deliverable",
    19: "Deliver Small: Scope, Timeline & Quality",
    20: "Client Communication Basics",
    # ── Gate 4: Rate Raise (Days 21-30) ──
    21: "Package Your Services — Mini Output",
    22: "Deliverable #3 — Second Portfolio Piece",
    23: "Specialization — Mini Output",
    24: "Long-Term Client Thinking",
    25: "Raise Your Rate: Packaging & Upsells",
    26: "Deliverable Excellence & Revisions",
    27: "Business Fundamentals — Mini Output",
    28: "Repeatable Systems — Mini Output",
    29: "Templates & Playbooks for Speed",
    30: "Graduation — Ready to Land Your First Client",
}


# ─── CORE GENERATOR ─────────────────────────────────────────

def generate_curriculum(topic_name: str, total_days: int = 30, platforms: list = None) -> list[dict]:
    """
    Generate a complete 30-day curriculum optimized for the contract-first arc.
    Platform days are interleaved at their gate positions (see _platform_day_for).
    Returns list of dicts with day_number, title, hook, concept, practice, retrieval,
    spaced_review, preview, video_title.
    """
    curriculum = []

    weekly_themes = [
        (1, "Ship Artifact #1", "Minimum skill to produce your first sellable deliverable"),
        (2, "Platform Live", "Profiles, gigs, and portfolio that make you findable"),
        (3, "First Order", "Proposals, delivering small, earning your first review"),
        (4, "Rate Raise", "Pricing up, repeat clients, and contract-readiness"),
    ]

    for day_num in range(1, total_days + 1):
        # Platform day interleaved at its gate position? Then use it.
        platform_day = _platform_day_for(day_num, platforms)
        if platform_day:
            curriculum.append(platform_day)
            continue

        # Determine week and theme
        week_num = min(4, (day_num - 1) // 7 + 1)
        week_theme, week_focus = weekly_themes[week_num - 1][1], weekly_themes[week_num - 1][2]

        # Determine focus for this specific day
        focus = _get_day_focus(day_num, week_num, week_theme, topic_name)
        objective = _get_learning_objective(day_num, week_num, topic_name)

        # Generate lesson via LLM
        lesson = _generate_daily_lesson(day_num, week_num, week_theme, focus, objective, topic_name,
                                        platforms=platforms)

        if lesson:
            # Phase 3: Contract-readiness quality check (regen once on failure)
            lesson = _quality_check(lesson, day_num, topic_name, platforms=platforms)
        if lesson:
            curriculum.append(lesson)
        else:
            # Fallback: structured lesson
            curriculum.append(_fallback_lesson(day_num, topic_name))

    return curriculum


def _generate_daily_lesson(day: int, week: int, week_theme: str, focus: str, objective: str, topic: str,
                           platforms: list = None) -> dict:
    """Generate a single day's lesson with all 6 sections.

    Injects the contract-arc milestone (gate) and the learner's linked
    platforms into the prompt so every lesson advances "land contract #1".
    """
    gate = _gate_for_day(day)
    if platforms:
        platforms_text = ", ".join(p.title() for p in platforms)
    else:
        platforms_text = "none linked yet — teach platform-agnostic skills; the artifact must be presentable on any platform"
    prompt = DAILY_LESSON_PROMPT.format(
        day=day, week=week, week_theme=week_theme,
        focus=focus, objective=objective, topic=topic,
        stage_theme=gate["name"], stage_days=f"{gate['start']}-{gate['end']}",
        platforms_text=platforms_text,
    )
    
    response = _call_llm(prompt)
    if not response:
        return None
    
    # Parse the 6 sections from the LLM response
    sections = _parse_lesson_sections(response)
    
    if not sections:
        return None
    
    title = _extract_title(sections.get("hook", ""), day, topic)
    
    lesson = {
        "day_number": day,
        "title": title,
        "hook": sections.get("hook", ""),
        "concept": sections.get("concept", ""),
        "practice": sections.get("practice", ""),
        "retrieval": sections.get("retrieval", ""),
        "spaced_review": sections.get("spaced_review", ""),
        "preview": sections.get("preview", ""),
        "video_title": f"{topic} — Day {day}: {title}",
        "description": sections.get("concept", "")[:300],
        "practice_task": sections.get("practice", "")[:200],
        "apply_task": f"Complete today's practice exercise and submit your work. Review: {sections.get('retrieval', '')[:100]}",
        "learning_objectives": f"Hook: {sections.get('hook', '')[:200]}",
    }
    
    return lesson


def _parse_lesson_sections(text: str) -> dict:
    """Parse the 6 sections from LLM output using heading markers."""
    sections = {
        "hook": "", "concept": "", "practice": "",
        "retrieval": "", "spaced_review": "", "preview": ""
    }
    
    # Try to split by ## headings
    current_section = None
    for line in text.split("\n"):
        stripped = line.strip()
        
        # Detect section headings
        lower = stripped.lower().replace("#", "").strip()
        
        if lower.startswith("hook"):
            current_section = "hook"
            continue
        elif lower.startswith("concept"):
            current_section = "concept"
            continue
        elif lower.startswith("practice"):
            current_section = "practice"
            continue
        elif lower.startswith("retrieval"):
            current_section = "retrieval"
            continue
        elif lower.startswith("spaced review") or lower.startswith("spaced"):
            current_section = "spaced_review"
            continue
        elif lower.startswith("preview"):
            current_section = "preview"
            continue
        
        if current_section and stripped:
            sections[current_section] += stripped + "\n"
    
    # Clean up
    for key in sections:
        sections[key] = sections[key].strip()
    
    # Check we got at least the main sections
    has_content = any(len(v) > 50 for v in sections.values())
    return sections if has_content else None


def _quality_check(lesson: dict, day: int, topic: str, platforms: list = None) -> dict:
    """Phase 3: Contract-readiness quality gate.

    Deterministic checks always run (sections present, title not generic).
    LLM scoring runs when ENABLE_QUALITY_SCORE is truthy (default on). If the
    scored total is below the pass threshold, the lesson is regenerated once.
    Returns None if the lesson fails the gate after the retry (caller falls
    back). Never raises — scoring failures pass the lesson through (no-500).
    """
    if not lesson:
        return lesson

    # Deterministic gate — must be a complete 6-section lesson.
    if not _has_all_sections(lesson):
        logger.warning(f"[quality] Day {day} missing sections — rejected")
        return None
    if is_fallback_content(lesson):
        logger.warning(f"[quality] Day {day} matches generic/fallback pattern — rejected")
        return None

    # LLM scoring — best effort; failures pass through.
    try:
        enabled = current_app.config.get("ENABLE_QUALITY_SCORE", "1")
        if str(enabled).lower() in ("0", "false", "no", ""):
            return lesson

        prompt = QUALITY_SCORING_PROMPT.format(lesson_text=_lesson_to_text(lesson))
        resp = _call_llm(prompt)
        if not resp:
            return lesson

        score = _parse_score_json(resp)
        total = score.get("total")
        passed = score.get("pass", True)
        if isinstance(total, (int, float)) and total >= 75 or passed:
            return lesson

        # Regen once and return the retry (no re-score — bounded cost).
        logger.warning(f"[quality] Day {day} scored {total}/100 — regenerating")
        gate = _gate_for_day(day)
        week = min(4, (day - 1) // 7 + 1)
        retry = _generate_daily_lesson(day, week, gate["name"],
                                       _get_day_focus(day, week, gate["name"], topic),
                                       _get_learning_objective(day, week, topic),
                                       topic, platforms=platforms)
        if retry and _has_all_sections(retry):
            return retry
        logger.warning(f"[quality] Day {day} retry failed gate — returning fallback")
        return None
    except Exception as e:
        logger.warning(f"[quality] Day {day} scoring error: {e}")
        return lesson


def _has_all_sections(lesson: dict) -> bool:
    """True if the lesson has all 6 content sections with text."""
    return all(lesson.get(k) for k in
               ("hook", "concept", "practice", "retrieval", "spaced_review", "preview"))


def _lesson_to_text(lesson: dict) -> str:
    """Flatten a lesson dict into the section-labeled text used for scoring."""
    return "\n\n".join(f"{k.upper()}: {lesson.get(k, '')}" for k in
                       ("hook", "concept", "practice", "retrieval", "spaced_review", "preview"))


def _parse_score_json(text: str) -> dict:
    """Parse the LLM scoring response into a dict. Robust to markdown fences."""
    try:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start:end + 1]
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _extract_title(hook_text: str, day: int, topic: str) -> str:
    """Extract or generate a short title from the hook section."""
    # Try to get the first meaningful sentence
    if hook_text:
        sentences = hook_text.split(".")
        for s in sentences:
            s = s.strip()
            if len(s) > 15 and len(s) < 120:
                return s
    return f"Day {day}: {topic} Fundamentals"


def _get_day_focus(day: int, week: int, theme: str, topic: str) -> str:
    """Get the specific focus for a day based on the contract-first arc."""
    return _DAY_FOCUS.get(day, f"{theme} — Day {day} focus")


def _get_learning_objective(day: int, week: int, topic: str) -> str:
    """Generate a Bloom's taxonomy learning objective for the day."""
    bloom_verbs = {1: ["Build", "Produce", "Assemble"], 2: ["Create", "Draft", "Publish"],
                   3: ["Send", "Deliver", "Pitch"], 4: ["Raise", "Systemize", "Optimize"]}
    verbs = bloom_verbs.get(week, ["Apply", "Create"])
    import random
    verb = random.choice(verbs)
    return f"{verb} key {topic} output that a client would pay for"


def _fallback_lesson(day: int, topic: str) -> dict:
    """Generate a structured fallback lesson when LLM is unavailable.
    Produces day-specific content using the weekly theme framework so each
    day feels distinct even without AI generation."""
    week_num = min(4, (day - 1) // 7 + 1)
    day_in_week = ((day - 1) % 7) + 1

    week_meta = {
        1: {"theme": "Ship Artifact #1", "desc_prefix": "building the minimum skill to produce a sellable deliverable",
            "practice_prefix": "hands-on build toward Deliverable #1",
            "apply_prefix": "publish Deliverable #1 to your portfolio"},
        2: {"theme": "Platform Live", "desc_prefix": "making your freelance offering findable",
            "practice_prefix": "portfolio/profile preparation exercise",
            "apply_prefix": "create or update a live gig/profile/portfolio"},
        3: {"theme": "First Order", "desc_prefix": "winning and delivering your first paid project",
            "practice_prefix": "proposal or buyer-request simulation",
            "apply_prefix": "send a real proposal or buyer request"},
        4: {"theme": "Rate Raise", "desc_prefix": "raising your rate and getting contract-ready",
            "practice_prefix": "pricing and packaging exercise",
            "apply_prefix": "update your rates and add an upsell package"},
    }
    wm = week_meta[week_num]
    focus = _get_day_focus(day, week_num, wm["theme"], topic)

    # Title: topic-specific, never generic "Part X"
    title = f"Day {day}: {focus} ({topic})"

    # Description: week+focus specific
    description = (
        f"Day {day} of your {topic} freelance journey — {wm['desc_prefix']}. "
        f"Today you focus on {focus.lower()}, a skill that directly helps you "
        f"land and deliver {topic} projects for paying clients."
    )

    # Hook: varies by week progression
    hooks = [
        f"Every {topic} freelancer started exactly where you are now — on Day {day}. "
        f"Today's {focus.lower()} lesson is the step that separates beginners from working pros.",
        f"What if you could master {focus.lower()} in just one focused session? "
        f"Day {day} of {topic} is designed to get you there with a real exercise.",
        f"Clients hiring for {topic} roles specifically look for {focus.lower()} skills. "
        f"Today you'll prove you have them — hands on keyboard, not just reading.",
    ]
    hook = hooks[day % len(hooks)]

    # Concept: topic + focus specific
    concept = (
        f"Today's core concept: {focus} in {topic} freelancing.\n\n"
        f"Understanding {focus.lower()} is essential because clients judge your "
        f"{topic} expertise by how well you handle this specific area. The best "
        f"{topic} freelancers don't just know the theory — they've practiced "
        f"applying {focus.lower()} in real project scenarios.\n\n"
        f"Key insight: {focus} connects directly to client outcomes. When you "
        f"master this, you can confidently pitch {topic} services at higher rates."
    )

    # Practice: day-specific exercise
    practices = [
        f"Setup & Configure: Set up your {topic} workspace with the tools needed for {focus.lower()}. "
        f"Document each step and save screenshots for your portfolio.",
        f"Build a Mini-Project: Create a small {topic} project focused on {focus.lower()}. "
        f"It should demonstrate your understanding and be presentable to a client.",
        f"Analyze a Real Example: Find a real-world {topic} project that uses {focus.lower()}. "
        f"Break down what they did well and what you'd improve.",
        f"Create a Template: Build a reusable template or checklist for {focus.lower()} in {topic} projects. "
        f"This becomes part of your freelance toolkit.",
        f"Solve a Client Scenario: Given this brief — 'I need {focus.lower()} for my {topic} project' — "
        f"outline your approach, deliverables, and timeline.",
    ]
    practice = practices[day % len(practices)]

    # Apply task: week-appropriate deliverable
    apply_tasks = {
        1: f"Document what you built today for {focus.lower()} and add it to your learning journal. "
           f"Write 3 sentences about how this skill helps {topic} clients.",
        2: f"Take your practice output and refine it into a portfolio-ready piece. "
           f"Screenshot the before/after and write a brief case study paragraph.",
        3: f"Draft a short proposal paragraph for a hypothetical {topic} client who needs {focus.lower()}. "
           f"Include your approach, timeline, and what makes you the right fit.",
        4: f"Compile your best {focus.lower()} work from this week into a single showcase piece. "
           f"Write a caption explaining your {topic} expertise to a potential client.",
    }
    apply_task = apply_tasks[week_num]

    # Learning objectives: Bloom's level per week (contract-first framing)
    bloom = {1: "Build and ship", 2: "Create and publish", 3: "Pitch and deliver", 4: "Raise and systemize"}
    learning_objectives = f"{bloom[week_num]} {focus.lower()} to land your first {topic} contract (Day {day}/30)"

    return {
        "day_number": day,
        "title": title,
        "hook": hook,
        "concept": concept,
        "practice": practice,
        "retrieval": (
            f"1. Write down the 3 most important {focus.lower()} concepts from today.\n"
            f"2. Explain {focus.lower()} to someone who has never used {topic}.\n"
            f"3. What's one thing about {focus.lower()} you still need to practice?"
        ),
        "spaced_review": (
            f"Yesterday you learned about {('core setup' if day == 2 else 'the previous topic')}. "
            f"Today's {focus.lower()} builds directly on that foundation. "
            f"How do they connect in a real {topic} project?"
        ),
        "preview": (
            f"Tomorrow's lesson takes {focus.lower()} further with advanced techniques "
            f"that impress {topic} clients."
        ),
        "video_title": f"{topic} — Day {day}: {focus}",
        "description": description,
        "practice_task": practice,
        "apply_task": apply_task,
        "learning_objectives": learning_objectives,
    }


def _call_llm(prompt: str) -> Optional[str]:
    """Call the LLM via the single-source config module (big-pickle → deepseek).

    Returns None fast when no API key is available (fallback content path).
    """
    from services.llm_config import call_llm
    return call_llm(prompt)


# ─── PLATFORM MODULES (research-backed, gate-ordered) ───────
# Each module is ordered to match the contract arc: activation days
# (profile/gig/portfolio) land in Gate 2, order-winning days in Gate 3,
# repeat-business days in Gate 4. Content mirrors research/fiverr_research.md,
# research/contra_research.md, and research/upwork_research.md.

PLATFORM_MODULES = {
    "upwork": {"name": "Upwork Proposal Mastery", "days": [
        {"title": "Profile Optimization for Upwork Search", "description": "Upwork's algorithm rewards complete profiles updated daily. Niche down to ONE platform/skill — not 'Digital Marketing Expert' but 'Meta Ads for DTC E-Commerce Brands'. Turn 'Available for work' ON — the algorithm favors it.",
         "practice_task": "Audit your profile title and overview against 3 top earners in your niche; rewrite your overview using Problem → Solution → Proof format.",
         "apply_task": "Update your Upwork title, overview, and skill list; turn availability ON.",
         "video_title": "Upwork Profile Optimization"},
        {"title": "Portfolio Presentation (Upwork-Specific)", "description": "Portfolio is everything for beginners — self-initiated projects count. Upload case studies showing process, not just final work: Problem → Approach → Result with a measurable outcome.",
         "practice_task": "Write 3 portfolio case studies using Problem → Approach → Result; add one measurable result line to each.",
         "apply_task": "Upload your case studies and link external work (GitHub, Gumroad, personal site) to your profile.",
         "video_title": "Upwork Portfolio"},
        {"title": "Writing Proposals That Convert", "description": "The first 2 lines decide everything. Open with the client's problem, not your resume. Reference a detail from their job post, ask a smart question, or show work already done. 2-3 paragraphs max, specific numbers, never AI-flavored.",
         "practice_task": "Rewrite 3 sample proposals: first 2 lines must name the client's problem; body = understanding + comparable proof + call to action.",
         "apply_task": "Submit 1 real proposal within 2-3 hours of a job posting — the golden window.",
         "video_title": "Upwork Proposals — The First 2 Lines"},
        {"title": "Pricing Strategy for New Upwork Freelancers", "description": "Start with $50-100 fixed-price projects to earn a 5-star review fast — trade margin for social proof. Then $15-25/hr, then $35-50+/hr within 6-12 months. Never lowball so far that serious clients doubt you.",
         "practice_task": "Calculate your minimum viable rate (target earnings / billable hours) and a first-review price 20-30% below market.",
         "apply_task": "Set your Upwork rates and create one $50-100 fixed-price offer.",
         "video_title": "Upwork Pricing Strategy"},
        {"title": "Handling Interviews & Client Communication", "description": "Reply within 10-20 minutes — clients talk to multiple freelancers at once. Keep first replies short: one smart question, no pricing talk initially.",
         "practice_task": "Role-play 3 client interview scenarios: draft first replies that show you read the job post.",
         "apply_task": "Respond to pending client messages and set up a notification schedule.",
         "video_title": "Upwork Interviews"},
        {"title": "Common Upwork Mistakes", "description": "AI-generated proposals are dead on arrival. Don't open with your resume, don't spray-and-pray, don't apply to jobs 24+ hours old, and walk away from red flags (vague scope, off-platform links, free-work requests).",
         "practice_task": "Audit your last 5 proposals against the mistake list; rewrite the weakest one.",
         "apply_task": "Fix weak proposals and target only 4-5 star clients with payment history.",
         "video_title": "10 Upwork Mistakes"},
        {"title": "Building JSS & Getting Repeat Clients", "description": "JSS > 90% unlocks Top Rated and consistent work. Fast responses, on-time delivery, and gentle post-delivery check-ins drive repeat clients — your largest source of ongoing income.",
         "practice_task": "Create a client communication schedule: delivery → check-in at day 3 → monthly value-add.",
         "apply_task": "Send a value-add message to a past or current client.",
         "video_title": "Upwork JSS & Repeat Clients"},
    ]},
    "fiverr": {"name": "Fiverr Gig Mastery", "days": [
        {"title": "Fiverr Gig Creation & SEO", "description": "Your gig title must match EXACTLY what buyers search — use Fiverr's autocomplete as your keyword source. The first 2 lines of your description are visible in search and must sell immediately.",
         "practice_task": "Research 5 top-selling gigs in your niche; extract their exact search terms; write 5 gig-title options.",
         "apply_task": "Create your first Fiverr gig with an SEO-matched title and a 2-line hook description.",
         "video_title": "Fiverr Gig SEO"},
        {"title": "Pricing Packages (Basic/Standard/Premium)", "description": "Basic = 70% of market (entry), Standard = market rate (most buyers pick this), Premium = 130% (comprehensive). Add gig extras: fast delivery, extra revisions, commercial use.",
         "practice_task": "Build your 3 packages with prices, delivery times, and revision counts.",
         "apply_task": "Configure the packages on your live gig.",
         "video_title": "Fiverr Packages"},
        {"title": "Buyer Request Mastery", "description": "Send 10+ buyer requests daily — Fiverr's proposal equivalent. Each reply must reference the buyer's specific need, never a template.",
         "practice_task": "Write 5 buyer-request responses that each reference the buyer's stated problem.",
         "apply_task": "Send 10 buyer requests today and tomorrow.",
         "video_title": "Fiverr Buyer Requests"},
        {"title": "First 5 Reviews Strategy", "description": "Price 20-30% below market for your first 5 orders, over-deliver on every one, then ask for a review 2-3 days after delivery. Review velocity boosts rank more than total count.",
         "practice_task": "Create a delivery checklist and a 3-step review-request message sequence.",
         "apply_task": "Offer your first 5 buyers a 50% custom-offer discount to secure orders fast.",
         "video_title": "Fiverr First 5 Reviews"},
        {"title": "Delivery Excellence & Review Generation", "description": "Order completion >90% is critical for ranking. Over-deliver (add something unexpected), deliver before the deadline, and request reviews on a 2-3 day delay — never immediately.",
         "practice_task": "Draft 3 professional delivery and review-request messages.",
         "apply_task": "Apply the delivery message sequence to your next order.",
         "video_title": "Fiverr Reviews"},
        {"title": "Handling Revisions & Disputes", "description": "Protect your completion rate: set revision policies up front, scope clearly in the gig FAQ, and resolve disputes by re-delivering or offering a revision — never arguing.",
         "practice_task": "Write revision policies and a gig FAQ covering scope, revisions, and file formats.",
         "apply_task": "Update your gig FAQ with the revision and scope policies.",
         "video_title": "Fiverr Disputes"},
        {"title": "Scaling from 1 Gig to 5 Gigs", "description": "Expand to related niches once you have reviews. Each new gig targets the next adjacent search term; cross-promote gigs in descriptions.",
         "practice_task": "Identify 3 related gig ideas by searching autocomplete for adjacent buyer needs.",
         "apply_task": "Create your second and third gigs.",
         "video_title": "Fiverr Scaling"},
    ]},
    "contra": {"name": "Contra Portfolio Success", "days": [
        {"title": "Portfolio Creation (Contra-Specific)", "description": "Contra is portfolio-first — the platform indexes portfolio items, not profiles. 3-5 items minimum, each with Problem → Approach → Result. Show process, not just final work.",
         "practice_task": "Write 3 portfolio case studies using the Problem → Approach → Result format.",
         "apply_task": "Upload the case studies to your Contra portfolio.",
         "video_title": "Contra Portfolio"},
        {"title": "Profile Optimization & Skills Targeting", "description": "Skill tags determine search visibility — use ALL relevant tags. Complete EVERY profile field; incomplete profiles rank lower. Set availability to 'Available now' for priority.",
         "practice_task": "Audit your Contra profile: list every field, tag, and link you're missing.",
         "apply_task": "Complete every missing field, add skill tags, link GitHub/Behance, and set 'Available now'.",
         "video_title": "Contra Profile"},
        {"title": "Pricing on a Commission-Free Platform", "description": "You keep 100% of earnings — price 15-20% higher than Upwork ($40-75/hr typical). Project-based pricing is preferred over hourly. Transparent pricing builds trust.",
         "practice_task": "Calculate your Contra rate at 15-20% above your Upwork/Fiverr rate; draft a project-based price list.",
         "apply_task": "Set your Contra pricing and availability status.",
         "video_title": "Contra Pricing"},
        {"title": "Client Communication & Negotiation", "description": "Clear scope definition is the #1 negotiation lever. Get the challenge, timeline, and tools in writing before quoting. Price based on the client's budget history, not your experience level.",
         "practice_task": "Write response templates for inquiries: scope questions, timeline, tools, deliverables.",
         "apply_task": "Apply your templates to pending inquiries.",
         "video_title": "Contra Communication"},
        {"title": "Building Long-Term Client Relationships", "description": "No commission means repeat clients are far more profitable. Deliver on time, send value-add messages, and become the go-to for adjacent work.",
         "practice_task": "Create a client follow-up schedule: post-delivery check-in, monthly value-add, referral ask.",
         "apply_task": "Send a value-add message to a past client.",
         "video_title": "Contra Repeat Business"},
    ]},
}


# ─── PLATFORM INTERLEAVE (gate positions) ───────────────────
# Platform days replace skill days at fixed slots inside the 30-day arc so the
# learner's platform is LIVE by Day 10 and producing first orders by Day 20.
# The PRIMARY linked platform (demand priority: upwork > fiverr > contra) gets
# its full module; secondary platforms contribute their activation days only
# (profile/gig/portfolio + first-order mechanics), keeping at least 17 skill days.

_PLATFORM_PRIORITY = {"upwork": 1, "fiverr": 2, "contra": 3}

_PLATFORM_FULL_SLOTS = {
    "upwork": [6, 8, 11, 13, 16, 21, 27],
    "fiverr": [7, 9, 12, 14, 17, 23, 28],
    "contra": [10, 15, 18, 20, 24],
}

_PLATFORM_ACTIVATION_SLOTS = {
    "upwork": [6, 8, 11],
    "fiverr": [7, 9, 12],
    "contra": [10, 15, 18],
}


def _build_platform_day(platform: str, day: dict, day_num: int) -> dict:
    """Expand a platform module day into the full 6-section lesson shape."""
    module_name = PLATFORM_MODULES[platform]["name"]
    return {
        "day_number": day_num,
        "title": day["title"],
        "video_title": day["video_title"],
        "description": day["description"],
        "practice_task": day["practice_task"],
        "apply_task": day["apply_task"],
        "hook": f"Today you'll learn {day['title']} — a key skill for winning contracts on {module_name}.",
        "concept": day["description"],
        "practice": day["practice_task"],
        "retrieval": ("1. What's the most important thing you learned today?\n"
                      "2. How will you apply this to your next order or proposal?\n"
                      "3. What's one thing you need more help with?"),
        "spaced_review": ("Think about how this platform strategy connects to the "
                          "portfolio artifact you've been building."),
        "preview": ("Tomorrow we'll build on this with another platform-specific strategy."),
        "is_platform_day": True,
    }


def _platform_day_for(day_num: int, platforms: list) -> dict:
    """Return the interleaved platform day for this day_number, or None.

    Primary platform uses its full slot table; secondary platforms use their
    activation-only slots (first 3 module days). Invalid platforms are ignored.
    """
    if not platforms:
        return None
    valid = [p for p in platforms if p in PLATFORM_MODULES]
    if not valid:
        return None
    ordered = sorted(valid, key=lambda p: _PLATFORM_PRIORITY.get(p, 99))
    primary, secondary = ordered[0], ordered[1:]

    for plat in [primary] + secondary:
        slots = (_PLATFORM_FULL_SLOTS if plat == primary else _PLATFORM_ACTIVATION_SLOTS).get(plat, [])
        if day_num in slots:
            idx = slots.index(day_num)
            module = PLATFORM_MODULES[plat]
            if idx < len(module["days"]):
                return _build_platform_day(plat, module["days"][idx], day_num)
    return None


def get_platform_day_count(platforms: list) -> int:
    """Total number of platform days interleaved for a platform list."""
    if not platforms:
        return 0
    valid = [p for p in platforms if p in PLATFORM_MODULES]
    if not valid:
        return 0
    ordered = sorted(valid, key=lambda p: _PLATFORM_PRIORITY.get(p, 99))
    count = len(PLATFORM_MODULES[ordered[0]]["days"])
    for plat in ordered[1:]:
        count += len(_PLATFORM_ACTIVATION_SLOTS.get(plat, []))
    return count


def _generate_platform_days(platforms: list) -> list[dict]:
    """Generate the interleaved platform-specific training days (gate order)."""
    if not platforms:
        return []
    days = []
    for day_num in range(1, 31):
        day = _platform_day_for(day_num, platforms)
        if day:
            days.append(day)
    return days


def _fallback_curriculum(topic: str, total_days: int = 30) -> list[dict]:
    """Deterministic fallback curriculum — no LLM, no platform interleave."""
    return [_fallback_lesson(day, topic) for day in range(1, total_days + 1)]
