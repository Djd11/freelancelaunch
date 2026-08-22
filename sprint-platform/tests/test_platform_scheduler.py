"""Tests for platform_scheduler — start, stop, status, manual trigger."""
import pytest
from unittest.mock import patch, MagicMock
from services.platform_scheduler import (
    start_scheduler, stop_scheduler, trigger_refresh_now, get_scheduler_status,
    _scheduler,
)
import services.platform_scheduler as sched_mod


# ─── Status ──────────────────────────────────────────────────────────

class TestSchedulerStatus:
    def test_status_when_not_started(self):
        """Returns not running when no scheduler exists."""
        sched_mod._scheduler = None
        status = get_scheduler_status()
        assert status["running"] is False
        assert status["jobs"] == []


# ─── Start / Stop ────────────────────────────────────────────────────

class TestStartStop:
    @patch("apscheduler.schedulers.background.BackgroundScheduler")
    def test_start_creates_scheduler(self, mock_bs_cls):
        """start_scheduler creates and starts a BackgroundScheduler."""
        sched_mod._scheduler = None
        mock_scheduler = MagicMock()
        mock_bs_cls.return_value = mock_scheduler
        app = MagicMock()
        start_scheduler(app)
        mock_scheduler.add_job.assert_called_once()
        mock_scheduler.start.assert_called_once()
        # Cleanup
        sched_mod._scheduler = None

    def test_start_does_not_duplicate(self):
        """Calling start twice does not create a second scheduler."""
        sched_mod._scheduler = MagicMock()
        sched_mod._scheduler.running = True
        app = MagicMock()
        with patch("apscheduler.schedulers.background.BackgroundScheduler") as mock_bs:
            start_scheduler(app)
            mock_bs.assert_not_called()
        sched_mod._scheduler = None

    def test_stop_shutdowns_scheduler(self):
        """stop_scheduler calls shutdown."""
        mock_scheduler = MagicMock()
        sched_mod._scheduler = mock_scheduler
        stop_scheduler()
        mock_scheduler.shutdown.assert_called_once_with(wait=False)
        assert sched_mod._scheduler is None


# ─── Manual Trigger ──────────────────────────────────────────────────

class TestTriggerRefresh:
    @patch("services.feed_ingest.refresh_all_platforms")
    @patch("services.supabase_client.get_supabase")
    def test_trigger_calls_refresh(self, mock_sb, mock_refresh):
        """trigger_refresh_now calls refresh_all_platforms."""
        mock_refresh.return_value = {"rss": {"new": 5, "skipped": 0, "error": None}}
        app = MagicMock()
        results = trigger_refresh_now(app)
        mock_refresh.assert_called_once()
        assert results["rss"]["new"] == 5

    @patch("services.feed_ingest.refresh_all_platforms")
    @patch("services.supabase_client.get_supabase")
    def test_trigger_returns_error_results(self, mock_sb, mock_refresh):
        """Errors per platform are returned in results."""
        mock_refresh.return_value = {"freelancer": {"new": 0, "skipped": 0, "error": "auth failed"}}
        app = MagicMock()
        results = trigger_refresh_now(app)
        assert results["freelancer"]["error"] == "auth failed"
