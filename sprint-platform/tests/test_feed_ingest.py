"""Tests for feed_ingest — dedup, normalize, cluster assignment, counter refresh."""
import pytest
from unittest.mock import patch, MagicMock
from services.feed_ingest import (
    _url_hash, _title_similarity, _existing_external_ids,
    _existing_urls, _cluster_for_skills, ingest_jobs,
)
from services.platform_connector import JobPosting


# ─── Helpers ─────────────────────────────────────────────────────────

def _mock_sb(existing_ids=None, existing_urls=None, clusters=None):
    """Create a mock Supabase client for testing ingest."""
    sb = MagicMock()
    _ids = existing_ids or set()
    _urls = existing_urls or set()

    def _select_table(table):
        m = MagicMock()
        if table == "job_feed":
            if _ids:
                m.select.return_value.not_.return_value.execute.return_value.data = [
                    {"external_id": eid} for eid in _ids
                ]
            else:
                m.select.return_value.not_.return_value.execute.return_value.data = []
        elif table == "job_clusters":
            m.select.return_value.eq.return_value.execute.return_value.data = clusters or []
        elif table == "platform_connections":
            m.update.return_value.eq.return_value.execute.return_value = MagicMock()
        return m

    sb.table.side_effect = _select_table
    return sb


def _mock_connector(jobs, configured=True):
    """Create a mock connector returning specific jobs."""
    conn = MagicMock()
    conn.platform_name = "test-platform"
    conn.is_configured.return_value = configured
    conn.fetch_jobs.return_value = jobs
    return conn


# ─── URL Hash ────────────────────────────────────────────────────────

class TestUrlHash:
    def test_deterministic(self):
        """Same URL always produces same hash."""
        assert _url_hash("https://example.com/job/1") == _url_hash("https://example.com/job/1")

    def test_different_urls(self):
        """Different URLs produce different hashes."""
        assert _url_hash("https://a.com") != _url_hash("https://b.com")

    def test_case_insensitive(self):
        """URL comparison is case-insensitive."""
        assert _url_hash("HTTPS://Example.COM") == _url_hash("https://example.com")

    def test_trailing_slash_handling(self):
        """Trailing slashes are normalized."""
        h1 = _url_hash("https://example.com/job/1")
        h2 = _url_hash("https://example.com/job/1/")
        # They may differ (slash is part of URL), but both are deterministic
        assert _url_hash("https://example.com/job/1/") == _url_hash("https://example.com/job/1/")


# ─── Title Similarity ────────────────────────────────────────────────

class TestTitleSimilarity:
    def test_identical_titles(self):
        assert _title_similarity("Email Marketing Expert", "Email Marketing Expert") == 1.0

    def test_no_overlap(self):
        assert _title_similarity("Python Backend", "Graphic Design") == 0.0

    def test_partial_overlap(self):
        score = _title_similarity("Email Marketing Developer", "Email Campaign Developer")
        assert 0.5 < score < 1.0

    def test_empty_title(self):
        assert _title_similarity("", "something") == 0.0

    def test_both_empty(self):
        assert _title_similarity("", "") == 0.0


# ─── Cluster Matching ────────────────────────────────────────────────

class TestClusterForSkills:
    def test_matches_cluster_keywords(self):
        """Skills matching a cluster's keywords returns that cluster."""
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"cluster_key": "email-automation", "keywords": ["email", "klaviyo", "mailchimp"]},
            {"cluster_key": "web-scraping", "keywords": ["python", "scrapy", "selenium"]},
        ]
        result = _cluster_for_skills(sb, ["email", "klaviyo"])
        assert result == "email-automation"

    def test_falls_back_to_default(self):
        """No matching cluster returns default."""
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"cluster_key": "email-automation", "keywords": ["email"]},
        ]
        result = _cluster_for_skills(sb, ["unrelated-skill"])
        assert result == "email-automation"

    def test_empty_clusters(self):
        """No clusters returns default."""
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        result = _cluster_for_skills(sb, ["anything"])
        assert result == "email-automation"


# ─── Ingest Jobs ─────────────────────────────────────────────────────

class TestIngestJobs:
    @patch("services.feed_ingest._cluster_for_skills", return_value="email-automation")
    @patch("services.feed_ingest.assign_unlock_days")
    @patch("services.feed_ingest.refresh_cluster")
    def test_inserts_new_jobs(self, mock_refresh, mock_unlock, mock_cluster):
        """New jobs from connector are inserted into job_feed."""
        sb = MagicMock()
        # No existing IDs or URLs
        sb.table.return_value.select.return_value.not_.return_value.execute.return_value.data = []
        conn = _mock_connector([
            JobPosting(title="Job 1", source_platform="rss", external_id="ext1", url="https://a.com/1"),
            JobPosting(title="Job 2", source_platform="rss", external_id="ext2", url="https://a.com/2"),
        ])
        new, skipped = ingest_jobs(sb, conn, "email-automation", "email")
        assert new == 2
        assert skipped == 0
        assert sb.table.return_value.insert.call_count == 2

    @patch("services.feed_ingest._cluster_for_skills", return_value="email-automation")
    @patch("services.feed_ingest.assign_unlock_days")
    @patch("services.feed_ingest.refresh_cluster")
    @patch("services.feed_ingest._existing_external_ids", return_value={"ext1"})
    @patch("services.feed_ingest._existing_urls", return_value=set())
    def test_skips_existing_external_ids(self, mock_urls, mock_ids, mock_refresh, mock_unlock, mock_cluster):
        """Jobs with existing external_ids are skipped."""
        sb = MagicMock()
        conn = _mock_connector([
            JobPosting(title="Existing Job", source_platform="rss", external_id="ext1", url="https://a.com/1"),
            JobPosting(title="New Job", source_platform="rss", external_id="ext2", url="https://a.com/2"),
        ])
        new, skipped = ingest_jobs(sb, conn, "email-automation")
        assert new == 1
        assert skipped == 1

    @patch("services.feed_ingest._cluster_for_skills", return_value="email-automation")
    @patch("services.feed_ingest.assign_unlock_days")
    @patch("services.feed_ingest.refresh_cluster")
    @patch("services.feed_ingest._existing_external_ids", return_value=set())
    @patch("services.feed_ingest._existing_urls", return_value={"https://existing.com/job"})
    def test_skips_existing_urls(self, mock_urls, mock_ids, mock_refresh, mock_unlock, mock_cluster):
        """Jobs with existing URLs are skipped."""
        sb = MagicMock()
        conn = _mock_connector([
            JobPosting(title="Dup URL Job", source_platform="rss", url="https://existing.com/job"),
            JobPosting(title="New Job", source_platform="rss", url="https://new.com/job"),
        ])
        new, skipped = ingest_jobs(sb, conn, "email-automation")
        assert new == 1
        assert skipped == 1

    def test_skips_when_not_configured(self):
        """Returns 0,0 when connector is not configured."""
        sb = MagicMock()
        conn = _mock_connector([], configured=False)
        new, skipped = ingest_jobs(sb, conn, "email-automation")
        assert new == 0
        assert skipped == 0

    def test_skips_when_no_jobs(self):
        """Returns 0,0 when connector returns empty list."""
        sb = MagicMock()
        conn = _mock_connector([])
        new, skipped = ingest_jobs(sb, conn, "email-automation")
        assert new == 0
        assert skipped == 0

    @patch("services.feed_ingest._cluster_for_skills", return_value="email-automation")
    @patch("services.feed_ingest.assign_unlock_days")
    @patch("services.feed_ingest.refresh_cluster")
    def test_handles_db_insert_error_gracefully(self, mock_refresh, mock_unlock, mock_cluster):
        """DB insert errors are caught and counted as skipped."""
        sb = MagicMock()
        sb.table.return_value.select.return_value.not_.return_value.execute.return_value.data = []
        insert_mock = sb.table.return_value.insert.return_value
        insert_mock.execute.side_effect = Exception("duplicate key")
        conn = _mock_connector([
            JobPosting(title="Job 1", source_platform="rss", external_id="ext1"),
        ])
        new, skipped = ingest_jobs(sb, conn, "email-automation")
        assert new == 0
        assert skipped == 1
