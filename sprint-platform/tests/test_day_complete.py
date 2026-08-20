"""Tests that completing an already-completed day is a no-op."""
import pytest
from unittest.mock import patch, MagicMock


def test_already_completed_day_does_not_recompute_meter():
    """If a day is already done, complete_day must NOT recompute the meter."""
    from routes.sprints import _complete_day_if_not_done
    sb = MagicMock()
    sprint = {"id": "s1", "user_id": "u1", "cluster_key": "email-automation",
              "current_day": 3, "phase": "A"}
    sb.table.return_value.select.return_value.limit.return_value.execute.return_value.data = [
        {"is_done": True}
    ]
    result = _complete_day_if_not_done(sb, sprint, 3)
    assert result["already_done"] is True
    assert result.get("meter") is None
    sb.table.return_value.update.assert_not_called()


def _make_sb_with_is_done(is_done):
    """Create a mock SB where the first execute() returns is_done status."""
    sb = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_eq1 = MagicMock()
    mock_eq2 = MagicMock()
    mock_limit = MagicMock()

    # Chain: table().select().eq().eq().limit().execute()
    sb.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq1
    mock_eq1.eq.return_value = mock_eq2
    mock_eq2.limit.return_value = mock_limit
    mock_limit.execute.return_value = MagicMock(data=[{"is_done": is_done}])
    return sb


def test_first_completion_updates_and_advances():
    """First time completing a day must mark is_done=True and advance current_day."""
    from routes.sprints import _complete_day_if_not_done
    sb = _make_sb_with_is_done(is_done=False)
    sprint = {"id": "s1", "user_id": "u1", "cluster_key": "email-automation",
              "current_day": 3, "phase": "A"}
    with patch("routes.sprints.recompute", return_value={
        "newly_unlocked": 10, "unlocked_count": 50, "total_in_cluster": 450
    }):
        with patch("routes.sprints.load_momentum", return_value={"day_streak": 2, "confidence": 60}):
            with patch("routes.sprints.recompute_confidence", return_value=65):
                result = _complete_day_if_not_done(sb, sprint, 3)
    assert result["already_done"] is False
    assert result["meter"] is not None
    assert result["next_day"] == 4


def test_day_14_marks_sprint_completed():
    """Completing day 14 must set sprint status='completed'."""
    from routes.sprints import _complete_day_if_not_done
    sb = _make_sb_with_is_done(is_done=False)
    sprint = {"id": "s1", "user_id": "u1", "cluster_key": "email-automation",
              "current_day": 14, "phase": "C"}
    with patch("routes.sprints.recompute", return_value={
        "newly_unlocked": 5, "unlocked_count": 450, "total_in_cluster": 450
    }):
        with patch("routes.sprints.load_momentum", return_value={"day_streak": 13, "confidence": 90}):
            with patch("routes.sprints.recompute_confidence", return_value=95):
                result = _complete_day_if_not_done(sb, sprint, 14)
    assert result["already_done"] is False
    assert result["next_day"] == 14


def test_day_14_already_done_is_noop():
    """Completing an already-completed Day 14 should not recompute meter."""
    from routes.sprints import _complete_day_if_not_done
    sb = MagicMock()
    sprint = {"id": "s1", "user_id": "u1", "cluster_key": "email-automation",
              "current_day": 14, "phase": "C"}
    sb.table.return_value.select.return_value.limit.return_value.execute.return_value.data = [
        {"is_done": True}
    ]
    result = _complete_day_if_not_done(sb, sprint, 14)
    assert result["already_done"] is True
    assert result.get("meter") is None
    sb.table.return_value.update.assert_not_called()
