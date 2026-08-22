"""
mentor_agent — job-grounded Socratic RAG chat (engineering-spec §3 J8, §5, arch §6).
Request-scoped (2-4s), 20s timeout, LLM-only: asks the shared LLM provider
chain (services/llm.py) and — if it returns None or its answer is not grounded
in the target job's exact terminology — raises LLMGenerationError so the route
surfaces a visible error. There is no deterministic guided template: content is
never substituted when the LLM is unavailable.
"""
import re

from services.llm import call_llm, LLMGenerationError

FORBIDDEN_PATTERNS = [
    "I have built",
    "I've built",
    "here is the complete",
    "here's the complete",
    "the finished",
    "the implementation is",
    "the code is",
    "```",
]

MIN_ANSWER_LENGTH = 30


def _extract_terms(job_description):
    """Extract domain-specific terms from the job description for grounding.
    Filters out generic/common words and focuses on tool names, methodologies,
    and domain-specific vocabulary."""
    if not job_description:
        return []

    GENERIC = {
        "the", "this", "that", "with", "from", "have", "will", "been",
        "were", "they", "their", "about", "into", "over", "such", "your",
        "you", "and", "for", "are", "not", "but", "can", "may", "our",
        "who", "what", "when", "where", "how", "which", "would", "could",
        "should", "these", "those", "than", "them", "then", "some",
        "also", "just", "only", "very", "more", "most", "each", "does",
        "did", "any", "its", "all", "being", "there", "here", "other",
        "make", "like", "need", "work", "team", "new", "use", "used",
        "using", "best", "good", "able", "well", "know", "help", "look",
        "find", "give", "part", "take", "come", "back", "want", "way",
    }

    words = re.findall(r"[a-zA-Z][a-zA-Z \-]{2,}", job_description.lower())
    terms = []
    for w in words:
        w = w.strip()
        if w in GENERIC or len(w) < 4:
            continue
        if w not in terms:
            terms.append(w)
        if len(terms) >= 6:
            break
    return terms


def _build_prompt(question, job_description, terms, history=None):
    prompt = (
        "You are a Socratic mentor for a freelancer completing a 14-day sprint. "
        "The learner's target job posting says: "
        f"{job_description!r}. "
    )
    if history:
        prompt += "Earlier in this conversation:\n"
        for turn in history:
            if turn.get("role") == "user":
                prompt += f"- learner asked: {turn.get('text', '')!r}\n"
            elif turn.get("role") == "mentor":
                prompt += f"- you answered: {turn.get('text', '')!r}\n"
    prompt += (
        f"The learner now asks: {question!r}. "
        "Reply with guiding questions and hints that use the job posting's exact "
        "terminology. Never provide the finished implementation — coach the learner "
        "to discover it. Keep it under 120 words."
    )
    return prompt


def _grounded(candidate, terms):
    """Safety gate: an LLM answer must:
    1. Echo at least one job term (when terms exist)
    2. Never hand over the finished answer
    3. Be long enough to be substantive (>30 chars)
    4. Not be pure code blocks
    """
    if not candidate:
        return False
    if len(candidate.strip()) < MIN_ANSWER_LENGTH:
        return False
    lowered = candidate.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.lower() in lowered:
            return False
    if terms and not any(t in lowered for t in terms):
        return False
    return True


def answer(question, job_description=None, history=None):
    """Return a guided, job-grounded LLM answer. Never hands over the finished
    answer. Raises LLMGenerationError when no provider answered or the answer
    failed the grounding gate — the route surfaces a visible error (LLM-only,
    no deterministic template). history is a list of {"role", "text"} prior
    turns so the mentor can reference the learner's earlier exchange."""
    job_description = job_description or ""
    terms = _extract_terms(job_description)

    candidate = call_llm(_build_prompt(question, job_description, terms, history), timeout=30, max_retries=3, backoff_base=2)
    if not candidate:
        raise LLMGenerationError("No LLM provider answered the mentor turn")
    if not _grounded(candidate, terms):
        raise LLMGenerationError("The LLM answer was not grounded in the target job's terminology")

    return {
        "answer": candidate,
        "guided": True,
        "grounded_in": terms,
    }
