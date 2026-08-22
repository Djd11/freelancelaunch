"""
platform_connector — per-platform adapter layer for freelance job feeds.

Each connector implements fetch_jobs() → List[JobPosting]. The feed ingest
pipeline (feed_ingest.py) calls connectors and normalizes the output into
the existing job_feed table.

Connectors:
  - RSSConnector: Remote OK, We Work Remotely, Remotive (free, no auth)
  - FreelancerConnector: Freelancer.com API (free tier, 10K calls/mo)
  - UpworkConnector: stub — activates when partnership keys are provided
  - ManualConnector: wraps existing admin-curated entries
"""
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class JobPosting:
    """Normalized job posting from any platform."""
    title: str
    company: str = ""
    url: str = ""
    description: str = ""
    skills: List[str] = field(default_factory=list)
    rate: Optional[float] = None
    experience: str = "intermediate"  # entry | intermediate | expert
    source_platform: str = "manual"
    external_id: str = ""
    posted_at: Optional[datetime] = None

    @property
    def dedup_key(self) -> str:
        """Stable dedup key: external_id if present, else URL hash."""
        if self.external_id:
            return f"{self.source_platform}:{self.external_id}"
        if self.url:
            return f"url:{hashlib.sha256(self.url.encode()).hexdigest()[:16]}"
        return f"title:{hashlib.sha256(self.title.lower().encode()).hexdigest()[:16]}"


class PlatformConnector(ABC):
    """Base class for all platform connectors."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Unique platform identifier."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """True if this connector has the required credentials/config."""
        ...

    @abstractmethod
    def fetch_jobs(self, query: str, max_results: int = 50) -> List[JobPosting]:
        """Fetch jobs matching the query. Returns normalized JobPosting list."""
        ...


# ─── RSS Connector ────────────────────────────────────────────────────


class RSSConnector(PlatformConnector):
    """Parse RSS feeds from remote job boards (Remote OK, WWR, Remotive)."""

    DEFAULT_FEEDS = {
        "remote-ok": "https://remoteok.com/remote-jobs.rss",
        "we-work-remotely": "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
        "remotive": "https://remotive.com/remote-jobs/feed",
    }

    def __init__(self, feed_urls: Optional[List[str]] = None):
        self.feed_urls = feed_urls if feed_urls is not None else list(self.DEFAULT_FEEDS.values())

    @property
    def platform_name(self) -> str:
        return "rss"

    @property
    def display_name(self) -> str:
        return "RSS Feeds (Remote OK, WWR, Remotive)"

    def is_configured(self) -> bool:
        return bool(self.feed_urls)

    def fetch_jobs(self, query: str, max_results: int = 50) -> List[JobPosting]:
        import feedparser
        jobs = []
        query_lower = query.lower()
        for feed_url in self.feed_urls:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:max_results]:
                    title = entry.get("title", "").strip()
                    if not title:
                        continue
                    # Basic keyword filter
                    summary = entry.get("summary", "") or ""
                    combined = f"{title} {summary}".lower()
                    if query_lower and not any(kw in combined for kw in query_lower.split()):
                        continue
                    skills = []
                    for tag in (entry.get("tags") if hasattr(entry, "get") else getattr(entry, "tags", [])) or []:
                        term = tag.get("term", "")
                        if term:
                            skills.append(term)
                    posted = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        try:
                            posted = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        except Exception:
                            pass
                    ext_id = entry.get("id", "") or entry.get("link", "")
                    jobs.append(JobPosting(
                        title=title,
                        company=entry.get("author", ""),
                        url=entry.get("link", ""),
                        description=summary[:2000],
                        skills=skills[:10],
                        source_platform="rss",
                        external_id=ext_id,
                        posted_at=posted,
                    ))
            except Exception as exc:
                logger.warning("RSS feed %s failed: %s", feed_url, exc)
        return jobs[:max_results]


# ─── Freelancer.com Connector ─────────────────────────────────────────


class FreelancerConnector(PlatformConnector):
    """Freelancer.com API — free tier, 10K calls/month."""

    BASE_URL = "https://www.freelancer.com/api"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    @property
    def platform_name(self) -> str:
        return "freelancer"

    @property
    def display_name(self) -> str:
        return "Freelancer.com"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def fetch_jobs(self, query: str, max_results: int = 50) -> List[JobPosting]:
        if not self.is_configured():
            return []
        import urllib.request
        import json
        url = f"{self.BASE_URL}/0.1/jobs/active/?query={query}&limit={max_results}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "FreelanceLaunch/1.0",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except Exception as exc:
            logger.warning("Freelancer.com API failed: %s", exc)
            return []

        jobs = []
        for item in data.get("projects", data.get("jobs", [])):
            jobs.append(JobPosting(
                title=item.get("title", ""),
                company=item.get("employer", {}).get("username", ""),
                url=f"https://www.freelancer.com/projects/{item.get('seo_url', item.get('id', ''))}",
                description=item.get("description", "")[:2000],
                skills=[s.get("name", "") for s in item.get("jobs", []) if s.get("name")],
                rate=float(item.get("budget", {}).get("minimum", 0)) or None,
                experience=_map_fl_experience(item.get("experience_level", "")),
                source_platform="freelancer",
                external_id=str(item.get("id", "")),
                posted_at=_parse_timestamp(item.get("time_submitted")),
            ))
        return jobs


def _map_fl_experience(level: str) -> str:
    level = (level or "").lower()
    if "entry" in level or "beginner" in level:
        return "entry"
    if "expert" in level or "advanced" in level:
        return "expert"
    return "intermediate"


def _parse_timestamp(ts) -> Optional[datetime]:
    if not ts:
        return None
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        pass
    return None


# ─── Upwork Connector (stub) ─────────────────────────────────────────


class UpworkConnector(PlatformConnector):
    """Upwork API — stub until partnership approval.

    To activate: provide UPWORK_API_KEY and UPWORK_API_SECRET env vars.
    """

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret

    @property
    def platform_name(self) -> str:
        return "upwork"

    @property
    def display_name(self) -> str:
        return "Upwork (requires partnership)"

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def fetch_jobs(self, query: str, max_results: int = 50) -> List[JobPosting]:
        if not self.is_configured():
            logger.info("Upwork connector not configured — skipping")
            return []
        # TODO: implement when Upwork partnership is approved
        # Will use Upwork API v3: GET /api/v3/search/jobs/trending
        logger.warning("Upwork API not yet implemented — partnership pending")
        return []


# ─── Manual Connector ────────────────────────────────────────────────


class ManualConnector(PlatformConnector):
    """Wraps existing admin-curated job_feed entries as JobPosting objects."""

    @property
    def platform_name(self) -> str:
        return "manual"

    @property
    def display_name(self) -> str:
        return "Manual (Admin Curated)"

    def is_configured(self) -> bool:
        return True

    def fetch_jobs(self, query: str, max_results: int = 50) -> List[JobPosting]:
        # Manual connector doesn't fetch — it reads from DB
        # This is called by feed_ingest to pull existing manual entries
        return []


# ─── Factory ─────────────────────────────────────────────────────────


def get_connector(platform: str, **kwargs) -> PlatformConnector:
    """Factory: return a connector instance for the given platform."""
    connectors = {
        "rss": lambda: RSSConnector(feed_urls=kwargs.get("feed_urls")),
        "freelancer": lambda: FreelancerConnector(api_key=kwargs.get("api_key", "")),
        "upwork": lambda: UpworkConnector(
            api_key=kwargs.get("api_key", ""),
            api_secret=kwargs.get("api_secret", ""),
        ),
        "manual": lambda: ManualConnector(),
    }
    factory = connectors.get(platform)
    if not factory:
        raise ValueError(f"Unknown platform: {platform}")
    return factory()


def get_all_connectors() -> List[PlatformConnector]:
    """Return all available connector instances."""
    import os
    return [
        RSSConnector(),
        FreelancerConnector(api_key=os.getenv("FREELANCER_API_KEY", "")),
        UpworkConnector(
            api_key=os.getenv("UPWORK_API_KEY", ""),
            api_secret=os.getenv("UPWORK_API_SECRET", ""),
        ),
        ManualConnector(),
    ]
