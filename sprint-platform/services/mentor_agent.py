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

FORBIDDEN_HANDOVER = "I have built it"


def _extract_terms(job_description):
    """Pull a few distinctive terms from the job description for grounding."""
    if not job_description:
        return []
    words = re.findall(r"[a-z][a-z ]{3,}", job_description.lower())
    terms = []
    for w in words:
        w = w.strip()
        if len(w) > 4 and w not in terms:
            terms.append(w)
        if len(terms) >= 4:
            break
    return terms


def _build_prompt(question, job_description, terms):
    return (
        "You are a Socratic mentor for a freelancer completing a 14-day sprint. "
        "The learner's target job posting says: "
        f"{job_description!r} "
        f"The learner asked: {question!r}. "
        "Reply with guiding questions and hints that use the job posting's exact "
        "terminology. Never provide the finished implementation — coach the learner "
        "to discover it. Keep it under 120 words."
    )


def _grounded(candidate, terms):
    """Safety gate: an LLM answer must echo at least one job term (when the job
    has distinctive terms) and must never hand over the finished answer."""
    if not candidate or FORBIDDEN_HANDOVER in candidate:
        return False
    lowered = candidate.lower()
    return (not terms) or any(t in lowered for t in terms)


def answer(question, job_description=None):
    """Return a guided, job-grounded LLM answer. Never hands over the finished
    answer. Raises LLMGenerationError when no provider answered or the answer
    failed the grounding gate — the route surfaces a visible error (LLM-only,
    no deterministic template)."""
    job_description = job_description or ""
    terms = _extract_terms(job_description)

    candidate = call_llm(_build_prompt(question, job_description, terms))
    if not candidate:
        raise LLMGenerationError("No LLM provider answered the mentor turn")
    if not _grounded(candidate, terms):
        raise LLMGenerationError("The LLM answer was not grounded in the target job's terminology")

    return {
        "answer": candidate,
        "guided": True,
        "grounded_in": terms,
    }
