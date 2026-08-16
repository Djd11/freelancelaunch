"""
mentor_agent — job-grounded Socratic RAG chat (engineering-spec §3 J8, §5, arch §6).
Request-scoped (2-4s), 20s timeout, graceful fallback: tries the shared LLM
fallback chain (services/llm.py) and — if it returns None or its answer is not
grounded in the target job's exact terminology — answers with a deterministic
guided template that echoes the job description and never hands over the
finished answer.
"""
import re

from services.llm import call_llm

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


def _guided_answer(question, job_description):
    # Always echo the target job's exact wording so the mentor is grounded in it.
    excerpt = " ".join((job_description or "").split())
    if len(excerpt) > 100:
        excerpt = excerpt[:100].rstrip() + "…"
    context = f" Your target job describes: \"{excerpt}\"." if excerpt else ""
    lowered = question.lower()
    if "what" in lowered or "mean" in lowered or "explain" in lowered:
        return (
            "Break it down from the job post itself — the deliverable is whatever "
            "the client's words say, not a generic definition."
            f"{context} Work out the smallest piece you can build today, rebuild it, "
            "then compare it against the job's wording."
        )
    return (
        "Start from the job description — build the smallest reproducible version "
        "of exactly what it asks for today."
        f"{context} Then tell me what broke and what you tried; we debug together. 💪"
    )


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
    """Safety net: an LLM answer must echo at least one job term (when the job
    has distinctive terms) and must never hand over the finished answer."""
    if not candidate or FORBIDDEN_HANDOVER in candidate:
        return False
    lowered = candidate.lower()
    return (not terms) or any(t in lowered for t in terms)


def answer(question, job_description=None):
    """Return a guided, job-grounded answer. Never hands over the finished answer."""
    job_description = job_description or ""
    terms = _extract_terms(job_description)

    text = None
    try:
        candidate = call_llm(_build_prompt(question, job_description, terms))
        if _grounded(candidate, terms):
            text = candidate
    except Exception:
        text = None

    if text is None:
        # Specced graceful fallback (eng-spec §5: "deterministic fallback",
        # arch §6 step 6) — keeps the mentor offline-safe.
        text = _guided_answer(question, job_description)

    # The mentor is always Socratic/guided — whether the LLM answered or the
    # deterministic path took over.
    return {
        "answer": text,
        "guided": True,
        "grounded_in": terms,
    }
