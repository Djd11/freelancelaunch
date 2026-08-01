"""
Unit tests for the nudge engine (streak, confidence, milestones, encouragement).
Run: python -m pytest tests/test_nudge_engine.py -v
"""
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.nudge_engine import (
    compute_streak, get_encouragement, get_milestone,
    get_nudges, compute_confidence, get_welcome_back
)


def test_streak_consecutive_days():
    today = date.today()
    dates = [today, today - timedelta(days=1), today - timedelta(days=2)]
    assert compute_streak(dates) == 3


def test_streak_resets_after_gap():
    today = date.today()
    dates = [today - timedelta(days=2), today - timedelta(days=3)]
    assert compute_streak(dates) == 0


def test_streak_grace_for_yesterday():
    today = date.today()
    dates = [today - timedelta(days=1), today - timedelta(days=2)]
    assert compute_streak(dates) == 2


def test_streak_empty():
    assert compute_streak([]) == 0


def test_encouragement_non_empty():
    for field in ("video_watched", "practice_completed", "apply_completed", "day_complete"):
        msg = get_encouragement(field)
        assert msg and len(msg) > 10


def test_milestone_week1():
    m = get_milestone(7, 7)
    assert m and "Week 1" in m["title"]


def test_milestone_streak3():
    m = get_milestone(4, 3)
    assert m and "3-Day Streak" in m["title"]


def test_no_milestone_random_day():
    assert get_milestone(12, 2) is None


def test_nudges_incomplete_practice():
    progress_days = {3: {"practice_completed": False}}
    nudges = get_nudges(progress_days, 3, 4)
    types = [n["type"] for n in nudges]
    assert "incomplete_practice" in types


def test_nudges_streak_encouragement():
    progress_days = {4: {"practice_completed": True}}
    nudges = get_nudges(progress_days, 4, 5)
    types = [n["type"] for n in nudges]
    assert "streak" in types


def test_confidence_10_days():
    c = compute_confidence(10, 5)
    assert c["score"] >= 30
    assert c["level"] in ("Getting Started", "Building Momentum")


def test_confidence_30_days_unstoppable():
    c = compute_confidence(30, 7)
    assert c["score"] >= 90
    assert c["level"] == "Unstoppable"


def test_confidence_zero():
    c = compute_confidence(0, 0)
    assert c["score"] == 0
    assert c["level"] == "Just Beginning"


def test_welcome_back():
    assert get_welcome_back(3, 5) is not None
    assert get_welcome_back(0, 5) is None
    assert get_welcome_back(1, 5) is None
