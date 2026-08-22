-- =====================================================================
-- Migration 002: Platform Connections + Feed Dedup
-- Adds: platform_connections table, source_platform/external_id to job_feed
-- Run in Supabase SQL Editor (idempotent).
-- =====================================================================

-- Platform API connections (API keys, quotas, sync status)
CREATE TABLE IF NOT EXISTS platform_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform TEXT NOT NULL,                -- 'rss' | 'freelancer' | 'upwork' | 'manual'
    display_name TEXT NOT NULL,
    config JSONB DEFAULT '{}',             -- {feed_urls: [...], api_key: ..., search_query: ...}
    is_active BOOLEAN DEFAULT TRUE,
    quota_remaining INT,
    quota_limit INT,
    last_synced_at TIMESTAMPTZ,
    last_error TEXT,
    sync_interval_hours INT DEFAULT 6,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_platform_connections_platform ON platform_connections(platform);

-- Add dedup columns to job_feed
ALTER TABLE job_feed ADD COLUMN IF NOT EXISTS source_platform TEXT DEFAULT 'manual';
ALTER TABLE job_feed ADD COLUMN IF NOT EXISTS external_id TEXT;

-- Unique constraint: no duplicate jobs from the same platform
-- (partial index — only enforced when external_id is not null)
-- First: remove duplicate external_id rows (keep oldest)
DELETE FROM job_feed j
USING (
    SELECT MIN(id::text) AS min_id
    FROM job_feed
    WHERE external_id IS NOT NULL
    GROUP BY source_platform, external_id
) d
WHERE j.id::text != d.min_id
AND j.external_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_job_feed_platform_dedup
    ON job_feed(source_platform, external_id)
    WHERE external_id IS NOT NULL;

-- Also dedup by URL when available
-- First: remove duplicate rows (keep the oldest row per source_url)
DELETE FROM job_feed j
USING (
    SELECT MIN(id::text) AS min_id
    FROM job_feed
    WHERE source_url IS NOT NULL
    GROUP BY source_url
) d
WHERE j.id::text != d.min_id
AND j.source_url IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_job_feed_url_dedup
    ON job_feed(source_url)
    WHERE source_url IS NOT NULL;
