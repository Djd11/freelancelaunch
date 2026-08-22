-- =====================================================================
-- Migration 002: Platform Connections + Feed Dedup
-- Run in Supabase SQL Editor (idempotent).
-- Uses DO blocks — no temp tables, handles all FK references.
-- =====================================================================

-- 1. Platform API connections table
CREATE TABLE IF NOT EXISTS platform_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform TEXT NOT NULL,
    display_name TEXT NOT NULL,
    config JSONB DEFAULT '{}',
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

-- 2. Add dedup columns to job_feed
ALTER TABLE job_feed ADD COLUMN IF NOT EXISTS source_platform TEXT DEFAULT 'manual';
ALTER TABLE job_feed ADD COLUMN IF NOT EXISTS external_id TEXT;

-- =====================================================================
-- 3. Dedup job_feed by source_url
--    FK tables referencing job_feed(id):
--      capstone_briefs.job_feed_id (NOT NULL)
--      proposals.job_feed_id (NOT NULL)
--      mentor_sessions.job_feed_id (nullable)
--    Strategy: re-point FKs → delete duplicates
-- =====================================================================

DO $$
DECLARE
    dup RECORD;
    keep_id UUID;
BEGIN
    FOR dup IN
        SELECT j.id AS dup_id,
               (SELECT j2.id
                FROM job_feed j2
                WHERE j2.source_url = j.source_url
                ORDER BY j2.posted_at ASC
                LIMIT 1) AS keep_id
        FROM job_feed j
        WHERE j.source_url IS NOT NULL
          AND j.id != (
              SELECT j2.id
              FROM job_feed j2
              WHERE j2.source_url = j.source_url
              ORDER BY j2.posted_at ASC
              LIMIT 1
          )
    LOOP
        -- Re-point FK references from duplicate → kept row
        UPDATE capstone_briefs SET job_feed_id = dup.keep_id WHERE job_feed_id = dup.dup_id;
        UPDATE proposals SET job_feed_id = dup.keep_id WHERE job_feed_id = dup.dup_id;
        UPDATE mentor_sessions SET job_feed_id = dup.keep_id WHERE job_feed_id = dup.dup_id;
        -- Delete the duplicate job_feed row
        DELETE FROM job_feed WHERE id = dup.dup_id;
    END LOOP;
END $$;

-- 4. Dedup job_feed by (source_platform, external_id)

DO $$
DECLARE
    dup RECORD;
BEGIN
    FOR dup IN
        SELECT j.id AS dup_id,
               (SELECT j2.id
                FROM job_feed j2
                WHERE j2.source_platform = j.source_platform
                  AND j2.external_id = j.external_id
                ORDER BY j2.posted_at ASC
                LIMIT 1) AS keep_id
        FROM job_feed j
        WHERE j.external_id IS NOT NULL
          AND j.id != (
              SELECT j2.id
              FROM job_feed j2
              WHERE j2.source_platform = j.source_platform
                AND j2.external_id = j.external_id
              ORDER BY j2.posted_at ASC
              LIMIT 1
          )
    LOOP
        UPDATE capstone_briefs SET job_feed_id = dup.keep_id WHERE job_feed_id = dup.dup_id;
        UPDATE proposals SET job_feed_id = dup.keep_id WHERE job_feed_id = dup.dup_id;
        UPDATE mentor_sessions SET job_feed_id = dup.keep_id WHERE job_feed_id = dup.dup_id;
        DELETE FROM job_feed WHERE id = dup.dup_id;
    END LOOP;
END $$;

-- 5. Create unique indexes (safe now — no duplicates, no FK violations)

CREATE UNIQUE INDEX IF NOT EXISTS idx_job_feed_url_dedup
    ON job_feed(source_url)
    WHERE source_url IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_job_feed_platform_dedup
    ON job_feed(source_platform, external_id)
    WHERE external_id IS NOT NULL;
