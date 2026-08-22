# Freelance Platform Integration — Implementation Plan

> **For agentic workers:** Use test-driven-development to implement this plan task-by-task.

**Goal:** Connect the sprint platform to real freelance job portals (RSS feeds, Freelancer.com API, Upwork-ready stub) so job data flows automatically instead of manual curation.

**Architecture:** 3-layer design: Platform Connectors (per-platform adapter) → Feed Ingest Pipeline (dedup + normalize) → Scheduler + Admin Dashboard.

**Tech Stack:** Python, feedparser (RSS), httpx (API calls), APScheduler (cron), existing Supabase DB.

**Spec:** docs/superpowers/specs/2026-08-22-freelance-platform-integration-design.md

---

## File Structure

| File | Responsibility |
|------|---------------|
| `services/platform_connector.py` | Base class + RSS/Freelancer/Upwork/Manual connectors |
| `services/feed_ingest.py` | Dedup, normalize, score, write to job_feed |
| `services/platform_scheduler.py` | APScheduler cron + refresh trigger |
| `routes/admin_platforms.py` | Admin dashboard: platform status, manual refresh |
| `templates/admin/platforms.html` | Admin UI for platform management |
| `tests/test_platform_connector.py` | Tests for connectors |
| `tests/test_feed_ingest.py` | Tests for ingest pipeline |
| `tests/test_platform_scheduler.py` | Tests for scheduler |
| `db/migrations/002_platform_connections.sql` | New table + job_feed columns |

---

## Tasks

### T1: DB migration — platform_connections table + job_feed columns
- Add `platform_connections` table (id, platform, api_key_encrypted, config JSONB, quota_remaining, last_synced_at, status)
- Add `source_platform` and `external_id` columns to `job_feed` for dedup
- Add unique index on `(source_platform, external_id)` where external_id is not null
- **Tests:** migration runs without error, constraints work

### T2: PlatformConnector base class + data model
- `JobPosting` dataclass: title, company, url, description, skills, rate, experience, source_platform, external_id, posted_at
- `PlatformConnector` ABC: `fetch_jobs(query, max_results) → List[JobPosting]`, `platform_name`, `is_configured`
- **Tests:** base class interface, JobPosting creation

### T3: RSSConnector (Remote OK, We Work Remotely, Remotive)
- Uses `feedparser` to parse RSS feeds
- Configurable feed URLs per cluster
- Normalizes RSS entries to JobPosting
- **Tests:** parse mock RSS XML → JobPosting objects, handle malformed feed

### T4: FreelancerConnector (Freelancer.com API)
- Uses httpx to call `GET /api/0.1/jobs/active/`
- API key from platform_connections table
- Normalizes API response to JobPosting
- **Tests:** mock API response → JobPosting, handle rate limit, handle auth failure

### T5: UpworkConnector stub (ready for partnership approval)
- Stub that raises `NotConfigured` until API keys are provided
- Follows same interface, ready to activate
- **Tests:** raises NotConfigured, activates when keys present

### T6: ManualConnector (existing admin feed)
- Wraps existing admin-curated job_feed entries
- Returns them as JobPosting objects for unified pipeline
- **Tests:** reads existing manual entries

### T7: Feed ingest pipeline
- `ingest_feed(sb, connector, cluster_key, query)` → fetches, deduplicates (by URL hash + title similarity), normalizes, writes to job_feed, refreshes cluster counters
- Dedup: skip if `source_platform + external_id` already exists, or if URL matches
- **Tests:** dedup prevents duplicates, new jobs added, cluster counters updated

### T8: Platform scheduler
- APScheduler BackgroundScheduler with configurable intervals
- `refresh_all_platforms(sb)` → loops through active connections, calls ingest
- `refresh_platform(sb, platform_name)` → single platform refresh
- **Tests:** scheduler runs, refresh triggers ingest, error handling

### T9: Admin dashboard + routes
- `GET /admin/platforms` → list connections, status, last sync, quota
- `POST /admin/platforms/<id>/refresh` → trigger manual refresh
- `POST /admin/platforms` → add new connection
- **Tests:** routes return 200, refresh triggers background job

### T10: Wire into app.py + cron
- Register admin_platforms blueprint
- Start scheduler on app startup (if APScheduler available)
- Add nightly cron endpoint for Render
- **Tests:** app starts with scheduler, cron endpoint works
