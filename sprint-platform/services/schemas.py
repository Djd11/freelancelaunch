"""Pydantic schemas for validating LLM-generated payloads before DB storage."""
from pydantic import BaseModel, Field
from typing import Optional


class LessonPayload(BaseModel):
    title: str
    objective: str
    script: str
    key_points: list[str] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)
    # Engagement preview fields (video-preview plan) — all OPTIONAL so legacy
    # payloads (which lack them) still validate. Clamping of pre_quiz answer
    # indices lives in services.lesson_engine, not here.
    hook: str | None = None
    day_overview: list[str] | None = None
    usefulness_context: str | None = None
    pre_quiz: list[dict] | None = None  # each: {"q": str, "options": list[str], "answer": int (0-based)}


class ProjectAnatomy(BaseModel):
    title: str
    source_url: Optional[str] = None
    clone_steps: list[str]
    rubric: list[dict] = Field(default_factory=list)


class ProposalDraft(BaseModel):
    opening_hook: str
    proof_sentence: str
    call_to_action: str
    score: int = -1  # -1 = LLM failure


class CaseStudy(BaseModel):
    problem: str
    solution: str
    result: str
