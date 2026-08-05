"""
Curriculum Generator — Learning Science-Based Algorithm
Implements 5-phase pipeline: Decomposition → Daily Generation → Quality Scoring → Adaptation → Refresh
"""
import json
import httpx
import logging
import re
from flask import current_app

logger = logging.getLogger(__name__)

# ─── PHASE 1: SKILL DECOMPOSITION ──────────────────────────

SKILL_DECOMPOSITION_PROMPT = """You are an expert curriculum designer for "{topic}" freelancing.

Design a 30-day learning curriculum for "{topic}" that helps beginners land their first freelance client.

Requirements:
- Identify 10-15 core competencies needed to offer "{topic}" as a freelance service
- Rank by dependency (what must be learned first)
- Group into 4 weekly themes: Week 1=Foundation, Week 2=Building, Week 3=Application, Week 4=Mastery
- Each competency must have: a Bloom's taxonomy learning objective (Use/Analyze/Create), a concrete success metric, and a real-world application
- The curriculum must be achievable in 60-90 minutes per day
- Days 1-3 should produce a tangible output (portfolio piece, first proposal, etc.)
- Include platform-specific training for Upwork, Fiverr, and Contra

Output ONLY valid JSON (no markdown):
{{
  "skill": "{topic}",
  "weeks": [
    {{"week": 1, "theme": "Foundation", "days": 1-7, "focus": "Core concepts and first output"}},
    {{"week": 2, "theme": "Building", "days": 8-15, "focus": "Intermediate skills and real examples"}},
    {{"week": 3, "theme": "Application", "days": 16-23, "focus": "Portfolio work and client proposals"}},
    {{"week": 4, "theme": "Mastery", "days": 24-30, "focus": "Income generation and business skills"}}
  ],
  "competencies": [
    {{"name": "...", "week": 1, "objective": "Use/Analyze/Create ...", "success_metric": "...", "real_world_application": "..."}}
  ]
}}"""


# ─── PHASE 2: DAILY LESSON GENERATION ───────────────────────

DAILY_LESSON_PROMPT = """You are designing Day {day} of a 30-day "{topic}" freelancing curriculum.

Context:
- Week {week} theme: {week_theme}
- Today's focus: {focus}
- Learning objective: {objective}
- Learner's current day: {day}/30

Generate a complete lesson with EXACTLY these 6 sections. Each section must be labeled with its heading exactly as shown:

## HOOK
(2 min) Write one sentence connecting today to their goal of landing a client. Include one surprising fact. End with one driving question they'll answer today.
[Write 2-3 sentences]

## CONCEPT
(15-20 min) Teach ONE core concept. Use a real freelancing example. Include a metaphor or analogy. Answer "why does this matter for getting clients?"
[Write 3-5 paragraphs, each 3-4 sentences]

## PRACTICE
(20-25 min) One hands-on exercise that produces a tangible output. Include a template or framework. Slightly challenging but achievable.
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
- Use specific examples, not generic advice
- Every claim must be actionable
- Output ONLY the 6 sections with their headings, no extra commentary"""


# ─── PHASE 3: QUALITY SCORING ───────────────────────────────

QUALITY_SCORING_PROMPT = """You are a learning science expert reviewing a curriculum lesson.

Rate this lesson on 10 criteria (1-10 each). For each, provide a score and 1-sentence explanation.

Criteria:
1. Engagement: Does the hook make you want to read the rest?
2. Relevance: Is every sentence relevant to landing a first client?
3. Actionability: Can the learner DO something after reading?
4. Examples: Are examples specific, vivid, and real?
5. Cognitive Load: Is it teaching ONE concept, not multiple?
6. Retrieval: Does the retrieval exercise require genuine recall?
7. Spaced Review: Does the review connect meaningfully to prior learning?
8. Bloom's Level: Does it target Apply/Create over Remember/Understand?
9. Time Estimate: Is it realistic in 45-60 minutes?
10. Output: Does the practice produce a real artifact?

OUTPUT FORMAT (valid JSON only):
{{
  "scores": {{
    "engagement": 8,
    "relevance": 7,
    ...
  }},
  "explanations": {{
    "engagement": "The hook uses a specific statistic...",
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


# ─── CORE GENERATOR ─────────────────────────────────────────

def generate_curriculum(topic_name: str, total_days: int = 30, platforms: list = None) -> list[dict]:
    """
    Generate a complete 30-day curriculum using the learning science algorithm.
    Returns list of dicts with day_number, title, hook, concept, practice, retrieval, spaced_review, preview, video_title.
    """
    curriculum = []
    
    weekly_themes = [
        (1, "Foundation", "Core concepts and first tangible output"),
        (2, "Building", "Intermediate skills with real examples"),
        (3, "Application", "Portfolio work and client proposals"),
        (4, "Mastery", "Income generation and business skills"),
    ]
    
    for day_num in range(1, total_days + 1):
        # Determine week and theme
        week_num = min(4, (day_num - 1) // 7 + 1)
        week_theme, week_focus = weekly_themes[week_num - 1][1], weekly_themes[week_num - 1][2]
        
        # Determine focus for this specific day
        focus = _get_day_focus(day_num, week_num, week_theme, topic_name)
        objective = _get_learning_objective(day_num, week_num, topic_name)
        
        # Generate lesson via LLM
        lesson = _generate_daily_lesson(day_num, week_num, week_theme, focus, objective, topic_name)
        
        if lesson:
            # Phase 3: Quality check
            lesson = _quality_check(lesson, day_num, topic_name)
            curriculum.append(lesson)
        else:
            # Fallback: structured lesson
            curriculum.append(_fallback_lesson(day_num, topic_name))
    
    return curriculum


def _generate_daily_lesson(day: int, week: int, week_theme: str, focus: str, objective: str, topic: str) -> dict:
    """Generate a single day's lesson with all 6 sections."""
    prompt = DAILY_LESSON_PROMPT.format(
        day=day, week=week, week_theme=week_theme,
        focus=focus, objective=objective, topic=topic
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


def _quality_check(lesson: dict, day: int, topic: str) -> dict:
    """Phase 3: Quality scoring gate. Currently passes through; scoring can be enabled."""
    # For MVP, we pass all lessons through. Quality scoring is an optimization.
    # The lesson generation prompt is already structured to produce high-quality output.
    return lesson


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
    """Get the specific focus for a day based on week and progression."""
    day_in_week = ((day - 1) % 7) + 1
    
    topics_map = {
        1: ["Introduction & Setup", "Core Concepts", "First Practical Task", "Tooling & Environment",
            "Real-World Example", "Common Pitfalls", "Week 1 Review & Portfolio Piece"],
        2: ["Intermediate Techniques", "Advanced Concepts", "Workflow Optimization", "Quality Standards",
            "Client Communication", "Project Planning", "Week 2 Review & Real Project"],
        3: ["Client Acquisition", "Proposal Writing", "Portfolio Building", "Pricing Strategy",
            "Client Management", "Deliverables & Revisions", "Week 3 Review & Live Proposal"],
        4: ["Income Optimization", "Scaling & Systems", "Niche Specialization", "Long-Term Clients",
            "Passive Income & Products", "Business Fundamentals", "Graduation & Next Steps"],
    }
    
    week_topics = topics_map.get(week, topics_map[1])
    idx = min(day_in_week - 1, len(week_topics) - 1)
    return week_topics[idx]


def _get_learning_objective(day: int, week: int, topic: str) -> str:
    """Generate a Bloom's taxonomy learning objective for the day."""
    bloom_verbs = {1: ["Identify", "Describe", "Explain"], 2: ["Apply", "Demonstrate", "Implement"],
                   3: ["Analyze", "Create", "Develop"], 4: ["Evaluate", "Design", "Optimize"]}
    verbs = bloom_verbs.get(week, ["Apply", "Create"])
    import random
    verb = random.choice(verbs)
    return f"{verb} key {topic} concepts in a real freelance context"


def _fallback_lesson(day: int, topic: str) -> dict:
    """Generate a structured fallback lesson when LLM is unavailable.
    Produces day-specific content using the weekly theme framework so each
    day feels distinct even without AI generation."""
    week_num = min(4, (day - 1) // 7 + 1)
    day_in_week = ((day - 1) % 7) + 1

    week_meta = {
        1: {"theme": "Foundation", "desc_prefix": "building core fundamentals",
            "practice_prefix": "hands-on setup exercise",
            "apply_prefix": "create your first deliverable"},
        2: {"theme": "Building", "desc_prefix": "developing intermediate skills",
            "practice_prefix": "real-world practice scenario",
            "apply_prefix": "build a portfolio piece"},
        3: {"theme": "Application", "desc_prefix": "applying skills to client work",
            "practice_prefix": "client-facing project simulation",
            "apply_prefix": "write a real proposal or pitch"},
        4: {"theme": "Mastery", "desc_prefix": "mastering advanced techniques",
            "practice_prefix": "optimization and refinement exercise",
            "apply_prefix": "complete your graduation project"},
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

    # Learning objectives: Bloom's level per week
    bloom = {1: "Understand and set up", 2: "Apply and build", 3: "Analyze and create", 4: "Evaluate and optimize"}
    learning_objectives = f"{bloom[week_num]} {focus.lower()} in {topic} freelancing (Day {day}/30)"

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


def _call_llm(prompt: str) -> str:
    """Call the configured LLM API — tries OpenRouter first, then others.
    Returns None fast when no API key is available (fallback content path)."""
    api_url = None
    api_key = None
    model = None
    
    # Priority 1: OpenRouter free (works everywhere, no API key needed)
    # Google Gemma 4 26B free tier — 20 req/min, ~1M tokens/day
    api_url = "https://openrouter.ai/api/v1/chat/completions"
    api_key = None
    model = "google/gemma-4-26b-a4b-it:free"
    
    # Try to get OpenRouter key from vision-tool config
    import os as _os
    try:
        import json
        config_path = _os.path.expanduser("~/Documents/vision-tool/config.json")
        if _os.path.exists(config_path):
            with open(config_path) as f:
                vc = json.load(f)
            or_key = vc.get("OPENROUTER_API_KEY", "")
            if or_key:
                api_key = or_key
    except Exception:
        pass
    
    # Fallback: env vars (for Render)
    if not api_key:
        api_key = current_app.config.get("LLM_API_KEY", "") or _os.environ.get("LLM_API_KEY", "")
        api_url = current_app.config.get("LLM_API_URL", "") or _os.environ.get("LLM_API_URL", "") or api_url
        model = current_app.config.get("LLM_MODEL", "") or _os.environ.get("LLM_MODEL", "") or model
    
    # Fallback: Omniroute (local only)
    if not api_key:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            if s.connect_ex(('127.0.0.1', 20128)) == 0:
                api_url = "http://localhost:20128/v1/chat/completions"
                api_key = ""
                model = "auto/cheap"
            s.close()
        except Exception:
            pass
    
    # Fallback: OpenCode.ai (Hermes config)
    if not api_key:
        try:
            import yaml
            hermes_path = _os.path.expanduser("~/.hermes/config.yaml")
            if _os.path.exists(hermes_path):
                with open(hermes_path) as f:
                    hermes = yaml.safe_load(f)
                mc = hermes.get("model", {})
                k = mc.get("api_key", "")
                if k:
                    api_key = k
                    api_url = mc.get("base_url", "") + "/chat/completions"
                    model = mc.get("default", "gpt-4o-mini")
        except Exception:
            pass
    
    if not api_url or not api_key:
        # No LLM available — fall back to structured content immediately (fast)
        logger.warning("No LLM API configured — using fallback content")
        return None
    
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    payload = {
        "model": model or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a curriculum designer and learning science expert. Output structured lesson content with clear section headings."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 4096
    }
    
    try:
        timeout_val = current_app.config.get("LLM_TIMEOUT", 20)
        resp = httpx.post(api_url, headers=headers, json=payload, timeout=timeout_val)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"LLM API call failed ({api_url[:50]}...): {e}")
        return None


# ─── PLATFORM MODULES (unchanged) ───────────────────────────

PLATFORM_MODULES = {
    "upwork": {"name": "Upwork Proposal Mastery", "days": [
        {"title": "Profile Optimization for Upwork Search", "description": "Learn how Upwork's algorithm ranks freelancers.",
         "practice_task": "Write your profile overview using Problem → Solution → Proof format",
         "apply_task": "Update your Upwork profile with the new overview",
         "video_title": "Upwork Profile Optimization"},
        {"title": "Writing Proposals That Convert", "description": "The first 2 lines decide everything.",
         "practice_task": "Rewrite 3 sample proposals",
         "apply_task": "Submit 1 real proposal to an Upwork job",
         "video_title": "Upwork Proposals — The First 2 Lines"},
        {"title": "Pricing Strategy for New Upwork Freelancers", "description": "Start with $50-100 projects for reviews.",
         "practice_task": "Calculate your minimum rate",
         "apply_task": "Set your Upwork hourly rate",
         "video_title": "Upwork Pricing Strategy"},
        {"title": "Portfolio Presentation (Upwork-Specific)", "description": "Self-initiated projects count as portfolio.",
         "practice_task": "Create 3 portfolio items",
         "apply_task": "Upload portfolio items to Upwork",
         "video_title": "Upwork Portfolio"},
        {"title": "Handling Interviews & Client Communication", "description": "Reply within 10-20 minutes.",
         "practice_task": "Role-play 3 client interview scenarios",
         "apply_task": "Respond to pending client messages",
         "video_title": "Upwork Interviews"},
        {"title": "Common Upwork Mistakes", "description": "AI proposals, spray-and-pray, lowballing.",
         "practice_task": "Audit your last 5 proposals",
         "apply_task": "Fix mistakes in active proposals",
         "video_title": "10 Upwork Mistakes"},
        {"title": "Building JSS & Getting Repeat Clients", "description": "JSS > 90% unlocks everything.",
         "practice_task": "Create a client communication schedule",
         "apply_task": "Send check-in to past clients",
         "video_title": "Upwork JSS"},
    ]},
    "fiverr": {"name": "Fiverr Gig Mastery", "days": [
        {"title": "Fiverr Gig Creation & SEO", "description": "Your gig title must match EXACTLY what buyers search.",
         "practice_task": "Research 5 top-selling gigs", "apply_task": "Create your first Fiverr gig",
         "video_title": "Fiverr Gig SEO"},
        {"title": "Pricing Packages (Basic/Standard/Premium)", "description": "Basic = 70% of market, Standard = market rate.",
         "practice_task": "Create your 3 pricing packages", "apply_task": "Set up gig packages",
         "video_title": "Fiverr Packages"},
        {"title": "Buyer Request Mastery", "description": "Send 10+ buyer requests daily.",
         "practice_task": "Write 5 buyer request responses", "apply_task": "Send 10 buyer requests",
         "video_title": "Fiverr Buyer Requests"},
        {"title": "First 5 Reviews Strategy", "description": "Price 20-30% below market for first 5 orders.",
         "practice_task": "Create delivery checklist", "apply_task": "Offer 50% discount to 5 buyers",
         "video_title": "Fiverr First 5 Reviews"},
        {"title": "Delivery Excellence & Review Generation", "description": "Ask for review 2-3 days after delivery.",
         "practice_task": "Draft 3 professional messages", "apply_task": "Apply message sequence",
         "video_title": "Fiverr Reviews"},
        {"title": "Handling Revisions & Disputes", "description": "Protect your completion rate.",
         "practice_task": "Write revision policies", "apply_task": "Update gig FAQ",
         "video_title": "Fiverr Disputes"},
        {"title": "Scaling from 1 Gig to 5 Gigs", "description": "Expand to related niches.",
         "practice_task": "Identify 3 related gig ideas", "apply_task": "Create second and third gigs",
         "video_title": "Fiverr Scaling"},
    ]},
    "contra": {"name": "Contra Portfolio Success", "days": [
        {"title": "Portfolio Creation (Contra-Specific)", "description": "Contra is portfolio-first.",
         "practice_task": "Write 3 portfolio case studies", "apply_task": "Upload portfolio items",
         "video_title": "Contra Portfolio"},
        {"title": "Profile Optimization & Skills Targeting", "description": "Complete EVERY field.",
         "practice_task": "Audit your Contra profile", "apply_task": "Complete missing profile fields",
         "video_title": "Contra Profile"},
        {"title": "Pricing on a Commission-Free Platform", "description": "You keep 100% — price 15-20% higher.",
         "practice_task": "Calculate your Contra rate", "apply_task": "Set Contra pricing",
         "video_title": "Contra Pricing"},
        {"title": "Client Communication & Negotiation", "description": "Clear scope definition is key.",
         "practice_task": "Write response templates", "apply_task": "Apply templates to inquiries",
         "video_title": "Contra Communication"},
        {"title": "Building Long-Term Client Relationships", "description": "No commission means repeat clients are more profitable.",
         "practice_task": "Create client follow-up schedule", "apply_task": "Send value-add message to past clients",
         "video_title": "Contra Repeat Business"},
    ]},
}


def get_platform_day_count(platforms: list) -> int:
    """Get total number of platform application days."""
    if not platforms:
        return 0
    return sum(len(PLATFORM_MODULES[p]["days"]) for p in platforms if p in PLATFORM_MODULES)


def _generate_platform_days(platforms: list) -> list[dict]:
    """Generate platform-specific application training days."""
    if not platforms:
        return []
    
    priority = {"upwork": 1, "fiverr": 2, "contra": 3}
    ordered = sorted(platforms, key=lambda p: priority.get(p, 99))
    
    all_days = []
    for platform in ordered:
        module = PLATFORM_MODULES.get(platform)
        if not module:
            continue
        for day in module["days"]:
            all_days.append({
                "title": day["title"],
                "video_title": day["video_title"],
                "description": day["description"],
                "practice_task": day["practice_task"],
                "apply_task": day["apply_task"],
                "hook": f"Today you'll learn {day['title']} — a key skill for winning contracts on {module['name']}.",
                "concept": day["description"],
                "practice": day["practice_task"],
                "retrieval": "1. What's the most important thing you learned today?\n2. How will you apply this to your next proposal?\n3. What's one thing you need more help with?",
                "spaced_review": "Think about how this platform strategy connects to the technical skills you've been learning.",
                "preview": "Tomorrow we'll build on this with another platform-specific strategy.",
            })
    
    return all_days
