"""Tests for platform_connector — base class, RSS, Freelancer, Upwork, Manual."""
import pytest
from unittest.mock import patch, MagicMock
from services.platform_connector import (
    JobPosting, PlatformConnector, RSSConnector,
    FreelancerConnector, UpworkConnector, ManualConnector,
    get_connector, get_all_connectors,
)


# ─── JobPosting ──────────────────────────────────────────────────────

class TestJobPosting:
    def test_basic_creation(self):
        jp = JobPosting(title="Test Job", company="Acme", url="https://example.com/1")
        assert jp.title == "Test Job"
        assert jp.company == "Acme"
        assert jp.source_platform == "manual"

    def test_dedup_key_with_external_id(self):
        jp = JobPosting(title="X", source_platform="rss", external_id="abc123")
        assert jp.dedup_key == "rss:abc123"

    def test_dedup_key_with_url(self):
        jp = JobPosting(title="X", url="https://example.com/job/1")
        assert jp.dedup_key.startswith("url:")

    def test_dedup_key_with_title_only(self):
        jp = JobPosting(title="Unique Job Title Here")
        assert jp.dedup_key.startswith("title:")

    def test_skills_default_empty(self):
        jp = JobPosting(title="X")
        assert jp.skills == []

    def test_rate_none_by_default(self):
        jp = JobPosting(title="X")
        assert jp.rate is None


# ─── RSSConnector ────────────────────────────────────────────────────

class TestRSSConnector:
    def test_platform_name(self):
        conn = RSSConnector()
        assert conn.platform_name == "rss"

    def test_is_configured_with_feeds(self):
        assert RSSConnector(feed_urls=["https://example.com/feed"]).is_configured()

    def test_is_configured_empty(self):
        """Empty list is not configured."""
        assert not RSSConnector(feed_urls=[]).is_configured()

    def test_default_feeds(self):
        conn = RSSConnector()
        assert len(conn.feed_urls) >= 2

    @patch("feedparser.parse")
    def test_fetch_jobs_parses_entries(self, mock_parse):
        entry1 = {"title": "Senior Email Developer", "link": "https://remoteok.com/job/123",
                   "summary": "Build email automation for Shopify stores",
                   "author": "TechCorp", "id": "remoteok-123",
                   "tags": [{"term": "python"}, {"term": "email"}]}
        entry2 = {"title": "Marketing Automation Engineer", "link": "https://remoteok.com/job/456",
                   "summary": "Klaviyo and Mailchimp email automation",
                   "author": "StartupInc", "id": "remoteok-456", "tags": []}
        mock_parse.return_value = MagicMock(entries=[entry1, entry2])
        conn = RSSConnector(feed_urls=["https://example.com/feed"])
        jobs = conn.fetch_jobs("", max_results=10)
        assert len(jobs) == 2
        assert jobs[0].title == "Senior Email Developer"
        assert jobs[0].company == "TechCorp"
        assert jobs[0].skills == ["python", "email"]
        assert jobs[0].source_platform == "rss"

    @patch("feedparser.parse")
    def test_fetch_jobs_filters_by_query(self, mock_parse):
        mock_parse.return_value = MagicMock(entries=[
            {"title": "Email Marketing Dev", "link": "http://a.com", "summary": "email campaigns", "id": "a"},
            {"title": "Python Backend Engineer", "link": "http://b.com", "summary": "fastapi postgres", "id": "b"},
            {"title": "Email Automation", "link": "http://c.com", "summary": "drip campaigns email", "id": "c"},
        ])
        conn = RSSConnector(feed_urls=["https://example.com/feed"])
        jobs = conn.fetch_jobs("email")
        assert len(jobs) == 2

    @patch("feedparser.parse")
    def test_fetch_jobs_handles_malformed_feed(self, mock_parse):
        mock_parse.side_effect = Exception("network error")
        conn = RSSConnector(feed_urls=["https://bad.example.com/feed"])
        jobs = conn.fetch_jobs("anything")
        assert jobs == []

    @patch("feedparser.parse")
    def test_fetch_jobs_skips_empty_titles(self, mock_parse):
        mock_parse.return_value = MagicMock(entries=[
            {"title": "", "link": "http://a.com", "summary": "x", "id": "a"},
            {"title": "Valid Job", "link": "http://b.com", "summary": "y", "id": "b"},
        ])
        conn = RSSConnector(feed_urls=["https://example.com/feed"])
        jobs = conn.fetch_jobs("")
        assert len(jobs) == 1
        assert jobs[0].title == "Valid Job"

    @patch("feedparser.parse")
    def test_fetch_multiple_feeds(self, mock_parse):
        call_count = [0]
        def side_effect(url):
            call_count[0] += 1
            return MagicMock(entries=[
                {"title": f"Job from feed {call_count[0]}", "link": f"http://{call_count[0]}.com", "id": f"id{call_count[0]}"},
            ])
        mock_parse.side_effect = side_effect
        conn = RSSConnector(feed_urls=["https://a.com/feed", "https://b.com/feed"])
        jobs = conn.fetch_jobs("")
        assert len(jobs) == 2


# ─── FreelancerConnector ─────────────────────────────────────────────

class TestFreelancerConnector:
    def test_platform_name(self):
        conn = FreelancerConnector()
        assert conn.platform_name == "freelancer"

    def test_not_configured_without_key(self):
        assert not FreelancerConnector().is_configured()

    def test_configured_with_key(self):
        assert FreelancerConnector(api_key="test-key").is_configured()

    def test_fetch_returns_empty_when_not_configured(self):
        conn = FreelancerConnector()
        jobs = conn.fetch_jobs("anything")
        assert jobs == []


# ─── UpworkConnector ─────────────────────────────────────────────────

class TestUpworkConnector:
    def test_platform_name(self):
        conn = UpworkConnector()
        assert conn.platform_name == "upwork"

    def test_not_configured_without_keys(self):
        assert not UpworkConnector().is_configured()

    def test_configured_with_keys(self):
        assert UpworkConnector(api_key="k", api_secret="s").is_configured()

    def test_fetch_returns_empty_when_not_configured(self):
        conn = UpworkConnector()
        jobs = conn.fetch_jobs("anything")
        assert jobs == []


# ─── ManualConnector ────────────────────────────────────────────────

class TestManualConnector:
    def test_platform_name(self):
        conn = ManualConnector()
        assert conn.platform_name == "manual"

    def test_always_configured(self):
        assert ManualConnector().is_configured()

    def test_fetch_returns_empty(self):
        conn = ManualConnector()
        jobs = conn.fetch_jobs("anything")
        assert jobs == []


# ─── Factory ─────────────────────────────────────────────────────────

class TestFactory:
    def test_get_connector_rss(self):
        conn = get_connector("rss")
        assert isinstance(conn, RSSConnector)

    def test_get_connector_freelancer(self):
        conn = get_connector("freelancer", api_key="test")
        assert isinstance(conn, FreelancerConnector)

    def test_get_connector_upwork(self):
        conn = get_connector("upwork", api_key="k", api_secret="s")
        assert isinstance(conn, UpworkConnector)

    def test_get_connector_manual(self):
        conn = get_connector("manual")
        assert isinstance(conn, ManualConnector)

    def test_get_connector_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown platform"):
            get_connector("nonexistent")

    def test_get_all_connectors(self):
        connectors = get_all_connectors()
        assert len(connectors) == 4
        names = [c.platform_name for c in connectors]
        assert "rss" in names
        assert "freelancer" in names
        assert "upwork" in names
        assert "manual" in names
