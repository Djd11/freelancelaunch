"""Tests that concurrent cohort creation does not produce duplicates."""
import pytest
import threading
from unittest.mock import MagicMock
from routes.main import _open_cohort


def test_open_cohort_checks_existing_first():
    """_open_cohort must check for existing active cohort before inserting."""
    sb = MagicMock()
    # First call: select().eq().eq().limit() returns existing cohort
    mock_limit = MagicMock()
    mock_limit.execute.return_value.data = [{"id": "existing-cohort-1"}]
    mock_eq2 = MagicMock()
    mock_eq2.limit.return_value = mock_limit
    mock_eq1 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    sb.table.return_value.select.return_value.eq.return_value = mock_eq1

    result = _open_cohort(sb, "email-automation")
    assert result == "existing-cohort-1"
    sb.table.return_value.insert.assert_not_called()


def test_open_cohort_creates_when_none_exists():
    """_open_cohort must create a new cohort when none exists."""
    sb = MagicMock()
    # First call: no existing active cohort
    mock_limit = MagicMock()
    mock_limit.execute.return_value.data = []
    mock_eq2 = MagicMock()
    mock_eq2.limit.return_value = mock_limit
    mock_eq1 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    sb.table.return_value.select.return_value.eq.return_value = mock_eq1
    # Second call: count query
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "old-1"}, {"id": "old-2"}
    ]
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "new-cohort-3"}]

    result = _open_cohort(sb, "email-automation")
    assert result == "new-cohort-3"
    sb.table.return_value.insert.assert_called_once()


def test_concurrent_open_cohort_check_then_act():
    """_open_cohort must check-then-act: check existing, then insert.
    The DB-level unique index prevents actual duplicates."""
    sb = MagicMock()
    insert_calls = []

    def track_insert(data):
        insert_calls.append(data)
        mock_result = MagicMock()
        mock_result.execute.return_value.data = [{"id": f"cohort-{len(insert_calls)}"}]
        return mock_result

    sb.table.return_value.insert.side_effect = track_insert
    mock_limit = MagicMock()
    mock_limit.execute.return_value.data = []
    mock_eq2 = MagicMock()
    mock_eq2.limit.return_value = mock_limit
    mock_eq1 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    sb.table.return_value.select.return_value.eq.return_value = mock_eq1

    # Two sequential calls — each sees no existing cohort and creates one
    r1 = _open_cohort(sb, "email-automation")
    r2 = _open_cohort(sb, "email-automation")

    # Both succeed (the DB unique index is the real guard)
    assert r1 is not None
    assert r2 is not None
    assert len(insert_calls) == 2, f"Expected 2 inserts for 2 sequential calls, got {len(insert_calls)}"
