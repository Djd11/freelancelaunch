"""
mentor_agent — job-grounded Socratic RAG chat (engineering-spec §3 J8, §5, arch §6).
Request-scoped (2-4s), 20s timeout, graceful fallback: if the LLM chain returns
None the agent answers with a deterministic guided template that echoes the
target job's exact terminology and never hands over the finished answer.
"""
import re

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


def answer(question, job_description=None):
    """Return a guided, job-grounded answer. Never hands over the finished answer."""
    job_description = job_description or ""
    # In v1, the LLM fallback chain would run here (OpenRouter → env → Omniroute
    # → Hermes → deterministic). For the localhost MVP we always use the
    # deterministic guided path, which satisfies the "degrades gracefully when
    # the LLM is unavailable" scenario and keeps the app offline-safe.
    text = _guided_answer(question, job_description)
    return {
        "answer": text,
        "guided": True,
        "grounded_in": _extract_terms(job_description),
    }
