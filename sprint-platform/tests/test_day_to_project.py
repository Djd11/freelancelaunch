"""Tests that DAY_TO_PROJECT is a single source of truth."""
import pytest


def test_day_to_project_is_single_source_of_truth():
    """Both modules must export the same mapping."""
    from routes import DAY_TO_PROJECT as routes_dtp
    from services.lesson_engine import DAY_TO_PROJECT as engine_dtp
    assert routes_dtp == engine_dtp


def test_day_to_project_has_expected_values():
    """Days 2-5 must map to projects 1, 1, 2, 3."""
    from routes import DAY_TO_PROJECT
    assert DAY_TO_PROJECT == {2: 1, 3: 1, 4: 2, 5: 3}


def test_all_phase_a_copywork_days_are_mapped():
    """Every Phase A copy-work day (2-5) must map to a project."""
    from routes import DAY_TO_PROJECT
    for day in [2, 3, 4, 5]:
        assert day in DAY_TO_PROJECT
        assert DAY_TO_PROJECT[day] in [1, 2, 3]
