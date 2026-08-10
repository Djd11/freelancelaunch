-- =====================================================================
-- FreelanceLaunch — Sprint Track schema (v2)
-- Additive to schema.sql (v1). Run in the Supabase SQL Editor after v1.
-- The Job Unlock Meter's source of truth is job_feed.unlock_day.
-- =====================================================================

-- ─── DEMAND / JOB FEED ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS job_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_key TEXT UNIQUE NOT NULL,      -- 'email-automation'
    display_name TEXT NOT NULL,            -- 'Email Automation'
    job_count INT DEFAULT 0,               -- live counter (450)
    avg_rate DECIMAL DEFAULT 0,
    growth_score DECIMAL DEFAULT 0,        -- +18% this quarter
    keywords TEXT[] DEFAULT '{}',
    last_synced_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS job_feed (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_key TEXT NOT NULL REFERENCES job_clusters(cluster_key) ON DELETE CASCADE,
    title TEXT NOT NULL,
    source TEXT,                            -- 'upwork' | 'fiverr' | 'contra' | 'curated'
    source_url TEXT,
    description TEXT,
    skills TEXT[] DEFAULT '{}',
    rate DECIMAL,                           -- posting value
    experience_needed TEXT,                 -- 'entry' | 'intermediate' | 'expert'
    review_count INT DEFAULT 0,             -- posting feedback count (unlock-curve signal)
    unlock_day INT NOT NULL,                -- 1..14 (quick-win + escalating curve)
    status TEXT DEFAULT 'active',
    posted_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_job_feed_cluster ON job_feed(cluster_key);
CREATE INDEX IF NOT EXISTS idx_job_feed_cluster_day ON job_feed(cluster_key, unlock_day);

-- Time-series of cluster job_count → powers live-counter history + trend
CREATE TABLE IF NOT EXISTS demand_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_key TEXT NOT NULL REFERENCES job_clusters(cluster_key) ON DELETE CASCADE,
    job_count INT NOT NULL,
    captured_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_demand_snapshots_cluster ON demand_snapshots(cluster_key, captured_at);

-- ─── SPRINTS ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sprints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    topic_id UUID REFERENCES topics(id) ON DELETE CASCADE,
    cluster_key TEXT NOT NULL REFERENCES job_clusters(cluster_key),
    phase TEXT DEFAULT 'A' CHECK (phase IN ('A','B','C')),
    current_day INT DEFAULT 1,             -- 1..14
    status TEXT DEFAULT 'active' CHECK (status IN ('active','paused','completed')),
    start_date DATE DEFAULT CURRENT_DATE,
    end_date DATE,
    badge_id UUID,                         -- set on completion (badges.id)
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sprints_user ON sprints(user_id);

CREATE TABLE IF NOT EXISTS sprint_days (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sprint_id UUID NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
    phase TEXT NOT NULL CHECK (phase IN ('A','B','C')),
    day_no INT NOT NULL,                   -- 1..14
    title TEXT NOT NULL,
    description TEXT,
    action_type TEXT NOT NULL,             -- 'copywork' | 'contract' | 'proposal' | 'gapfill'
    action_payload JSONB DEFAULT '{}',     -- e.g. {project_index:1} or {brief_id:...}
    curriculum_day_id UUID REFERENCES curriculum_days(id) ON DELETE SET NULL, -- optional Learn body
    is_done BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMPTZ,
    UNIQUE(sprint_id, day_no)
);
CREATE INDEX IF NOT EXISTS idx_sprint_days_sprint ON sprint_days(sprint_id, day_no);

-- ─── PHASE A: COPY-WORK ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS copywork_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sprint_id UUID NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
    project_index INT NOT NULL,            -- 1..3
    source_url TEXT NOT NULL,              -- the real project to replicate
    title TEXT NOT NULL,
    clone_steps JSONB DEFAULT '[]',        -- ordered replication checklist
    rubric JSONB DEFAULT '[]',             -- acceptance criteria (auto-checkable)
    gap_fill_topic TEXT,                   -- nuance flagged for Day 5
    done BOOLEAN DEFAULT FALSE,
    UNIQUE(sprint_id, project_index)
);

-- ─── PHASE B: MOCK CONTRACT ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS capstone_briefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sprint_id UUID NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
    job_feed_id UUID NOT NULL REFERENCES job_feed(id),   -- anonymized real posting
    title TEXT NOT NULL,
    requirements TEXT,
    constraints JSONB DEFAULT '{}',        -- {deadline_days:4, budget:180, notes:[...]}
    acceptance_criteria JSONB DEFAULT '[]',
    submission_url TEXT,
    verification_type TEXT DEFAULT 'auto' CHECK (verification_type IN ('auto','peer')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS verification_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capstone_brief_id UUID NOT NULL REFERENCES capstone_briefs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending','pass','fail')),
    reviewer_id UUID,                      -- null = automated
    feedback TEXT,
    reviewed_at TIMESTAMPTZ,
    UNIQUE(capstone_brief_id, user_id)
);

-- ─── PHASE C: PROPOSALS ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sprint_id UUID NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
    job_feed_id UUID NOT NULL REFERENCES job_feed(id),
    template_body TEXT,                    -- engineered proposal
    hooks JSONB DEFAULT '[]',              -- "I see you need X…"
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft','submitted')),
    score INT,                             -- completeness 0..100
    submitted_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_proposals_sprint ON proposals(sprint_id);

-- ─── BADGES ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    cluster_key TEXT NOT NULL,
    sprint_id UUID REFERENCES sprints(id) ON DELETE SET NULL,
    jobs_at_issue INT,                     -- live counter when issued
    issued_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, cluster_key)
);

-- ─── JOB UNLOCK METER (snapshot so the meter is O(1) to render) ─────

CREATE TABLE IF NOT EXISTS sprint_unlock_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sprint_id UUID NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    completed_days INT DEFAULT 0,
    unlocked_count INT DEFAULT 0,
    total_in_cluster INT DEFAULT 0,
    last_delta INT DEFAULT 0,              -- "+N" on the most recent day completion
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(sprint_id, user_id)
);

-- ─── AI MENTORSHIP ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS mentor_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    sprint_id UUID REFERENCES sprints(id) ON DELETE CASCADE,
    job_feed_id UUID REFERENCES job_feed(id),  -- context scope = the target job
    turn_json JSONB DEFAULT '[]',          -- chat turns
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
