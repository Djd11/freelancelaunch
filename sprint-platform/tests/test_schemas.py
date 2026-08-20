"""Tests that LLM output is validated against Pydantic schemas before storage."""
import pytest
from services.schemas import LessonPayload, ProjectAnatomy, ProposalDraft
from pydantic import ValidationError


def test_lesson_payload_requires_title():
    with pytest.raises(ValidationError, match="title"):
        LessonPayload(objective="Learn stuff", script="Do things")


def test_lesson_payload_requires_objective():
    with pytest.raises(ValidationError, match="objective"):
        LessonPayload(title="Day 1", script="Do things")


def test_lesson_payload_requires_script():
    with pytest.raises(ValidationError, match="script"):
        LessonPayload(title="Day 1", objective="Learn stuff")


def test_lesson_payload_accepts_valid():
    payload = LessonPayload(
        title="Day 1: Setup", objective="Learn basic setup",
        script="Step 1: Install Klaviyo...",
        key_points=["Install Klaviyo", "Connect Shopify"],
        pitfalls=["Don't skip the API key step"],
    )
    assert payload.title == "Day 1: Setup"
    assert len(payload.key_points) == 2


def test_lesson_payload_defaults_empty_lists():
    payload = LessonPayload(title="Day 1", objective="Learn", script="Do")
    assert payload.key_points == []
    assert payload.pitfalls == []


def test_project_anatomy_requires_title():
    with pytest.raises(ValidationError, match="title"):
        ProjectAnatomy(clone_steps=["step 1"])


def test_project_anatomy_requires_clone_steps():
    with pytest.raises(ValidationError, match="clone_steps"):
        ProjectAnatomy(title="Clone the flow")


def test_proposal_draft_requires_hook():
    with pytest.raises(ValidationError, match="opening_hook"):
        ProposalDraft(proof_sentence="I built this", call_to_action="Let's talk")
