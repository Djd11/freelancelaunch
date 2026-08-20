"""Tests that the mentor grounding gate rejects generic and handover answers."""
import pytest
from services.mentor_agent import _extract_terms, _grounded


KLAVIYO_JOB = (
    "We need a Klaviyo email automation specialist to build abandoned-cart "
    "flows, checkout recovery sequences, and win-back campaigns for "
    "Shopify stores using event-driven triggers."
)


def test_extract_terms_finds_domain_vocabulary():
    """Should extract domain-specific terms, not generic words."""
    terms = _extract_terms(KLAVIYO_JOB)
    assert len(terms) >= 3, f"Expected at least 3 terms, got {terms}"
    # Terms may be multi-word phrases; check that domain words appear in them
    all_text = " ".join(terms)
    for word in ["klaviyo", "abandoned-cart", "checkout", "shopify"]:
        assert word in all_text, f"Expected '{word}' in terms: {terms}"


def test_grounded_rejects_generic_answer():
    """An answer with no job terms should fail grounding."""
    terms = ["klaviyo", "abandoned-cart", "checkout", "win-back"]
    assert _grounded("That's a great question! Let me help you with that.", terms) is False


def test_grounded_rejects_handover():
    """An answer that hands over the finished implementation must fail."""
    terms = ["klaviyo", "abandoned-cart"]
    assert _grounded("I have built it for you. Here is the complete flow.", terms) is False


def test_grounded_rejects_code_block():
    """An answer that dumps code should be rejected."""
    terms = ["klaviyo", "abandoned-cart"]
    assert _grounded("```python\nflow = create_flow('abandoned-cart')\n```", terms) is False


def test_grounded_rejects_too_short_answer():
    """Very short answers are too thin to be grounded coaching."""
    terms = ["klaviyo", "abandoned-cart"]
    assert _grounded("Yes.", terms) is False


def test_grounded_passes_when_answer_uses_job_terms():
    """An answer that uses job-specific terms and is substantive should pass."""
    terms = ["klaviyo", "abandoned-cart", "checkout"]
    answer = (
        "To set up the Klaviyo abandoned-cart flow, start by creating a new "
        "flow triggered by the checkout started event. Think about what "
        "condition distinguishes an abandoned cart from a completed purchase."
    )
    assert _grounded(answer, terms) is True


def test_grounded_passes_with_empty_terms():
    """When the job has no distinctive terms, all substantive answers pass."""
    answer = (
        "That's an interesting approach. What do you think would happen "
        "if you tried a different trigger condition for the flow?"
    )
    assert _grounded(answer, []) is True
