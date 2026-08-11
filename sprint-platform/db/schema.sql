-- =====================================================================
-- FreelanceLaunch · Sprint Platform — Database Schema (PostgreSQL/Supabase)
-- Fresh project. Built from product-mockup.html (the product truth).
-- Deliberately NO freelance_pipeline table and NO v1 30-day curriculum tables.
-- The sprint record owns the whole outcome lifecycle (proposals → contracts).
--
-- ⚠️  TARGETS A NEW, SEPARATE Supabase project — NEVER the v1 project.
--    Several table names here (cohorts, contracts, badges, job_feed,
--    proposals, sprints, mentor) COLLIDE with the v1 schema.sql/schema_v2.sql.
--    Applying this to the v1 database would corrupt it. See
--    docs/supabase-setup.md for creating the dedicated project.
--
-- Run in the NEW project's Supabase SQL Editor (idempotent).
-- =====================================================================

-- ─── GUARD: refuse to run against the v1 database ─────────────────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_tables
    WHERE schemaname = 'public'
      AND tablename IN ('topics', 'curricula', 'freelance_pipeline',
                        'user_progress', 'cohort_videos', 'curriculum_days')
  ) THEN
    RAISE EXCEPTION
      'Sprint-Platform schema aborted: v1 tables (topics/curricula/freelance_pipeline) found. '
      'This schema must be applied to a NEW, dedicated Supabase project — never the v1 database. '
      'See docs/supabase-setup.md.';
  END IF;
END $$;

-- ─── USERS & PROFILES ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    headline TEXT,                        -- "Freelancer · Email Automation & Web Scraping"
    avatar_url TEXT,
    is_public BOOLEAN DEFAULT TRUE,       -- client-facing profile visibility (mockup screen 7)
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ─── DEMAND INTELLIGENCE ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS job_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_key TEXT UNIQUE NOT NULL,     -- 'email-automation'
    display_name TEXT NOT NULL,
    icon TEXT,
    description TEXT,
    job_count INT DEFAULT 0,              -- live counter ("450 jobs open")
    avg_rate DECIMAL DEFAULT 0,           -- median hourly rate ("$62/hr")
    growth_score DECIMAL DEFAULT 0,       -- "+18% demand this quarter"
    keywords TEXT[] DEFAULT '{}',
    status TEXT DEFAULT 'active' CHECK (status IN ('active','paused','archived')),
    last_synced_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS job_feed (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_key TEXT NOT NULL REFERENCES job_clusters(cluster_key) ON DELETE CASCADE,
    title TEXT NOT NULL,
    source TEXT,                          -- 'upwork' | 'fiverr' | 'contra' | 'curated'
    source_url TEXT,
    description TEXT,
    skills TEXT[] DEFAULT '{}',
    rate DECIMAL,
    experience_needed TEXT CHECK (experience_needed IN ('entry','intermediate','expert')),
    review_count INT DEFAULT 0,
    unlock_day INT NOT NULL,              -- 1..14 · quick-win + escalating value curve
    status TEXT DEFAULT 'active' CHECK (status IN ('active','filled','expired','archived')),
    posted_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_job_feed_cluster_day ON job_feed(cluster_key, unlock_day);

CREATE TABLE IF NOT EXISTS demand_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_key TEXT NOT NULL REFERENCES job_clusters(cluster_key) ON DELETE CASCADE,
    job_count INT NOT NULL,
    avg_rate DECIMAL,
    captured_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_demand_snapshots_cluster ON demand_snapshots(cluster_key, captured_at);

-- ─── COHORTS & SPRINTS ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS cohorts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_key TEXT NOT NULL REFERENCES job_clusters(cluster_key),
    name TEXT NOT NULL,                   -- "Cohort #12"
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status TEXT DEFAULT 'upcoming' CHECK (status IN ('upcoming','active','completed')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sprints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    cohort_id UUID REFERENCES cohorts(id) ON DELETE SET NULL,
    cluster_key TEXT NOT NULL REFERENCES job_clusters(cluster_key),
    phase TEXT DEFAULT 'A' CHECK (phase IN ('A','B','C')),
    current_day INT DEFAULT 1,            -- 1..14 (per-user pacing inside the cohort window)
    status TEXT DEFAULT 'active' CHECK (status IN ('active','paused','completed','abandoned')),
    badge_id UUID,                        -- set on completion (badges.id)

    -- Outcome lifecycle (the sprint owns this — pipeline removed by design)
    proposals_sent INT DEFAULT 0,
    responses_received INT DEFAULT 0,
    interviews_held INT DEFAULT 0,
    offers_received INT DEFAULT 0,
    contracts_won INT DEFAULT 0,
    contracts_completed INT DEFAULT 0,
    total_earned DECIMAL DEFAULT 0,
    avg_contract_value DECIMAL,
    first_contract_at TIMESTAMPTZ,
    repeat_clients INT DEFAULT 0,
    is_actively_seeking BOOLEAN DEFAULT TRUE,

    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_sprints_user ON sprints(user_id);
CREATE INDEX IF NOT EXISTS idx_sprints_cohort ON sprints(cohort_id);

CREATE TABLE IF NOT EXISTS sprint_days (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sprint_id UUID NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
    phase TEXT NOT NULL CHECK (phase IN ('A','B','C')),
    day_no INT NOT NULL,                  -- 1..14
    title TEXT NOT NULL,
    description TEXT,
    action_type TEXT NOT NULL CHECK (action_type IN ('setup','copywork','gapfill','contract','case-study','proposal')),
    action_payload JSONB DEFAULT '{}',
    is_done BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMPTZ,
    UNIQUE(sprint_id, day_no)
);
CREATE INDEX IF NOT EXISTS idx_sprint_days_sprint ON sprint_days(sprint_id, day_no);

-- ─── PHASE A: COPY-WORK + GAP-FILL ────────────────────────────────────

CREATE TABLE IF NOT EXISTS copywork_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sprint_id UUID NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
    project_index INT NOT NULL,           -- 1..3
    title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    clone_steps JSONB DEFAULT '[]',
    rubric JSONB DEFAULT '[]',            -- 3 acceptance criteria (auto-checkable)
    gap_fill_topic TEXT,                  -- nuance flagged → Day 5 micro-lesson
    done BOOLEAN DEFAULT FALSE,
    UNIQUE(sprint_id, project_index)
);

-- ─── VERIFICATION GATES (A→B and B→C) ────────────────────────────────
-- Gate 'A' = Phase A passes verification → Phase B unlocks
-- Gate 'B' = Mock Contract passes verification → Phase C unlocks

CREATE TABLE IF NOT EXISTS verification_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sprint_id UUID NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
    gate TEXT NOT NULL CHECK (gate IN ('A','B')),
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending','pass','fail')),
    verification_type TEXT DEFAULT 'auto' CHECK (verification_type IN ('auto','peer')),
    submitted_url TEXT,
    reviewer_id UUID REFERENCES auth.users(id),
    feedback TEXT,
    reviewed_at TIMESTAMPTZ,
    UNIQUE(sprint_id, gate)
);

-- ─── PHASE B: MOCK CONTRACT ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS capstone_briefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sprint_id UUID NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
    job_feed_id UUID NOT NULL REFERENCES job_feed(id),
    title TEXT NOT NULL,
    requirements TEXT,
    constraints JSONB DEFAULT '{}',       -- {deadline_days:4, budget:180, notes:[...]}
    acceptance_criteria JSONB DEFAULT '[]',
    verification_type TEXT DEFAULT 'auto' CHECK (verification_type IN ('auto','peer')),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ─── PHASE C: PROPOSALS & CONTRACTS ───────────────────────────────────

CREATE TABLE IF NOT EXISTS proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sprint_id UUID NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
    job_feed_id UUID NOT NULL REFERENCES job_feed(id),
    template_body TEXT,                   -- engineered proposal (hook + proof + CTA)
    hooks JSONB DEFAULT '[]',             -- "I see you need X…"
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft','submitted')),
    platform TEXT,                        -- 'upwork' | 'fiverr' | 'contra' | ...
    score INT,                            -- completeness 0..100
    submitted_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_proposals_sprint ON proposals(sprint_id);

CREATE TABLE IF NOT EXISTS contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sprint_id UUID NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    platform TEXT,
    client_name TEXT,
    project_title TEXT,
    contract_value DECIMAL,
    your_rate DECIMAL,
    hours_worked INT,
    start_date DATE,
    end_date DATE,
    status TEXT DEFAULT 'active' CHECK (status IN ('active','completed','cancelled')),
    is_repeat_client BOOLEAN DEFAULT FALSE,
    payment_received BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_contracts_sprint ON contracts(sprint_id);
CREATE INDEX IF NOT EXISTS idx_contracts_user ON contracts(user_id);

-- ─── BADGES & PUBLIC PROFILE (client loop) ────────────────────────────

CREATE TABLE IF NOT EXISTS badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    cluster_key TEXT NOT NULL,
    sprint_id UUID NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
    jobs_at_issue INT,                    -- live counter when issued
    issued_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, cluster_key)
);
CREATE INDEX IF NOT EXISTS idx_badges_cluster_age ON badges(cluster_key, issued_at);

-- Client-facing view: "filter freelancers by Completed [Skill] Sprint within 30 days"
CREATE OR REPLACE VIEW public_freelancers AS
    SELECT b.user_id, p.display_name, p.headline, p.avatar_url,
           b.cluster_key, c.display_name AS cluster_name,
           b.jobs_at_issue, b.issued_at,
           c.job_count AS jobs_now,
           s.proposals_sent, s.responses_received, s.interviews_held, s.contracts_won
    FROM badges b
    JOIN user_profiles p   ON p.user_id = b.user_id
    JOIN job_clusters c    ON c.cluster_key = b.cluster_key
    JOIN sprints s         ON s.id = b.sprint_id
    WHERE p.is_public = TRUE;

-- ─── JOB UNLOCK METER (snapshot so the meter is O(1) to render) ───────

CREATE TABLE IF NOT EXISTS sprint_unlock_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sprint_id UUID NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    completed_days INT DEFAULT 0,
    unlocked_count INT DEFAULT 0,
    total_in_cluster INT DEFAULT 0,
    last_delta INT DEFAULT 0,             -- "+N" on the most recent day completion
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(sprint_id, user_id)
);

-- ─── MOMENTUM ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_momentum (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    day_streak INT DEFAULT 0,
    best_streak INT DEFAULT 0,
    confidence INT DEFAULT 50 CHECK (confidence BETWEEN 0 AND 100),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ─── AI MENTOR ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS mentor_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    sprint_id UUID REFERENCES sprints(id) ON DELETE CASCADE,
    job_feed_id UUID REFERENCES job_feed(id),   -- context scope = the target job
    turn_json JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
