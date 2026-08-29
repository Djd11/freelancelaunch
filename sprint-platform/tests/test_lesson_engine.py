"""Tests for engagement-preview parsing/clamping and prompt injection.

Covers: _parse_json / clean_lesson returning + normalizing the four new
engagement fields, pre_quiz answer clamping (CRITIQUE #1), parity between the
two normalizers, and _ENGAGEMENT_INSTRUCTION being appended to every one of the
5 action_type branches of _lesson_prompt.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import lesson_engine as le


# ─── _parse_json engagement fields ────────────────────────────────────────

def test_parse_json_returns_engagement_fields():
    text = json.dumps({
        "title": "Day lesson", "objective": "obj", "script": "x" * 90,
        "key_points": ["a"], "pitfalls": ["b"],
        "quiz": ["q"], "quiz_answers": ["a"],
        "hook": "Land your first gig.",
        "day_overview": ["Configure trigger", "Build email"],
        "usefulness_context": "Clients ask for this.",
        "pre_quiz": [{"q": "What starts it?", "options": ["Checkout Started", "Refund"], "answer": 0}],
    })
    parsed = le._parse_json(text)
    assert parsed["hook"] == "Land your first gig."
    assert parsed["day_overview"] == ["Configure trigger", "Build email"]
    assert parsed["usefulness_context"] == "Clients ask for this."
    assert parsed["pre_quiz"][0]["answer"] == 0


def test_parse_json_missing_engagement_fields_become_empty():
    text = json.dumps({
        "title": "Day lesson", "objective": "obj", "script": "x" * 90,
        "key_points": ["a"], "pitfalls": ["b"], "quiz": ["q"], "quiz_answers": ["a"],
    })
    parsed = le._parse_json(text)
    assert parsed["hook"] == ""
    assert parsed["day_overview"] == []
    assert parsed["usefulness_context"] == ""
    assert parsed["pre_quiz"] == []


# ─── pre_quiz clamping (CRITIQUE #1) ──────────────────────────────────────

def _pq(answer, n_opts=2):
    return [{"q": "Q?", "options": [f"opt{i}" for i in range(n_opts)], "answer": answer}]


def test_pre_quiz_clamps_out_of_range_answer():
    text = json.dumps({
        "title": "t", "objective": "o", "script": "x" * 90,
        "key_points": ["a"], "pitfalls": ["b"], "quiz": ["q"], "quiz_answers": ["a"],
        "pre_quiz": _pq(5),   # 5 >= len(options)=2 -> drop
    })
    parsed = le._parse_json(text)
    assert parsed["pre_quiz"] == []


def test_pre_quiz_clamps_negative_answer():
    text = json.dumps({
        "title": "t", "objective": "o", "script": "x" * 90,
        "key_points": ["a"], "pitfalls": ["b"], "quiz": ["q"], "quiz_answers": ["a"],
        "pre_quiz": _pq(-1),
    })
    parsed = le._parse_json(text)
    assert parsed["pre_quiz"] == []


def test_pre_quiz_clamps_non_int_answer():
    text = json.dumps({
        "title": "t", "objective": "o", "script": "x" * 90,
        "key_points": ["a"], "pitfalls": ["b"], "quiz": ["q"], "quiz_answers": ["a"],
        "pre_quiz": _pq("1-based-oops"),
    })
    parsed = le._parse_json(text)
    assert parsed["pre_quiz"] == []


def test_pre_quiz_keeps_valid_answer():
    text = json.dumps({
        "title": "t", "objective": "o", "script": "x" * 90,
        "key_points": ["a"], "pitfalls": ["b"], "quiz": ["q"], "quiz_answers": ["a"],
        "pre_quiz": _pq(1, n_opts=2),
    })
    parsed = le._parse_json(text)
    assert len(parsed["pre_quiz"]) == 1
    assert parsed["pre_quiz"][0]["answer"] == 1


def test_pre_quiz_drops_single_option_items():
    text = json.dumps({
        "title": "t", "objective": "o", "script": "x" * 90,
        "key_points": ["a"], "pitfalls": ["b"], "quiz": ["q"], "quiz_answers": ["a"],
        # only 1 option -> needs >=2 -> drop
        "pre_quiz": [{"q": "Q?", "options": ["only-one"], "answer": 0}],
    })
    parsed = le._parse_json(text)
    assert parsed["pre_quiz"] == []


# ─── clean_lesson parity ──────────────────────────────────────────────────

def test_clean_lesson_parity_with_parse_json():
    raw = {
        "title": "t", "objective": "o", "script": "line1\\nline2",
        "key_points": ["a"], "pitfalls": ["b"], "quiz": ["q"], "quiz_answers": ["a"],
        "hook": "Hook here",
        "day_overview": ["one", "two"],
        "usefulness_context": "useful",
        # valid + one out-of-range (dropped)
        "pre_quiz": [{"q": "Q?", "options": ["a", "b"], "answer": 0},
                     {"q": "Bad?", "options": ["x", "y"], "answer": 9}],
    }
    cleaned = le.clean_lesson(raw)
    parsed = le._parse_json(json.dumps(raw))
    assert cleaned["hook"] == parsed["hook"] == "Hook here"
    assert cleaned["day_overview"] == parsed["day_overview"] == ["one", "two"]
    assert cleaned["usefulness_context"] == parsed["usefulness_context"] == "useful"
    assert cleaned["pre_quiz"] == parsed["pre_quiz"]
    assert len(cleaned["pre_quiz"]) == 1


def test_clean_lesson_normalizes_escapes():
    raw = {"title": "t\\n!", "objective": "o", "script": "s",
           "pre_quiz": [{"q": "Q?", "options": ["a", "b"], "answer": 0}]}
    cleaned = le.clean_lesson(raw)
    assert cleaned["title"] == "t\n!"


# ─── _ENGAGEMENT_INSTRUCTION present on all 5 branches ───────────────────

def test_engagement_instruction_present_all_branches():
    assert "hook" in le._ENGAGEMENT_INSTRUCTION
    assert "day_overview" in le._ENGAGEMENT_INSTRUCTION
    assert "usefulness_context" in le._ENGAGEMENT_INSTRUCTION
    assert "pre_quiz" in le._ENGAGEMENT_INSTRUCTION
    for action_type in ("setup", "copywork", "contract", "case-study", "proposal"):
        prompt = le._lesson_prompt(
            {"title": "Klaviyo flow setup for store", "description": "posting"},
            3, action_type, "Project 1",
            domain_context="use ONLY these tools",
        )
        assert le._ENGAGEMENT_INSTRUCTION in prompt, f"missing on branch {action_type}"
