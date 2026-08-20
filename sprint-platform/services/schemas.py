"""Pydantic schemas for validating LLM-generated payloads before DB storage."""
from pydantic import BaseModel, Field
from typing import Optional


class LessonPayload(BaseModel):
    title: str
    objective: str
    script: str
    key_points: list[str] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)


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
