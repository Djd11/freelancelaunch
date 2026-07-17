"""
FreelanceLaunch — Database Schema (PostgreSQL for Supabase)

Run this in the Supabase SQL Editor to create all tables.
"""

-- ─── FUNNEL 1: PLATFORM ACQUISITION ──────────────────────────

CREATE TABLE IF NOT EXISTS user_acquisition (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    source TEXT,                  -- 'youtube' | 'google' | 'reddit' | 'referral' | 'direct'
    source_detail TEXT,           -- 'youtube:video_id_abc123' | 'referral:user_x'
    utm_campaign TEXT,
    landing_topic TEXT,
    referred_by UUID REFERENCES auth.users(id),
    signed_up_at TIMESTAMPTZ DEFAULT now(),
    joined_cohort_at TIMESTAMPTZ,
    converted_to_paid_at TIMESTAMPTZ,
    tier TEXT DEFAULT 'free',     -- 'free' | 'guided' | 'placement'
    referral_count INT DEFAULT 0,
    lifetime_value DECIMAL DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);

-- ─── TOPICS ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    demand_score INT DEFAULT 50,
    job_count INT DEFAULT 0,
    avg_rate DECIMAL DEFAULT 0,
    thumbnail_url TEXT,
    is_curated BOOLEAN DEFAULT TRUE,
    status TEXT DEFAULT 'active', -- 'active' | 'paused' | 'archived'
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ─── CURRICULA ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS curricula (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID REFERENCES topics(id) ON DELETE CASCADE,
    total_days INT DEFAULT 30,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS curriculum_days (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id UUID REFERENCES curricula(id) ON DELETE CASCADE,
    day_number INT NOT NULL,       -- 1-30 or 1-60
    title TEXT NOT NULL,
    description TEXT,
    learning_objectives TEXT,
    practice_task TEXT,
    apply_task TEXT,
    video_title TEXT,
    video_script TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(curriculum_id, day_number)
);

-- ─── COHORTS ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS cohorts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID REFERENCES topics(id) ON DELETE CASCADE,
    curriculum_id UUID REFERENCES curricula(id) ON DELETE CASCADE,
    name TEXT NOT NULL,            -- "Web Scraping - July 2026"
    start_date DATE NOT NULL,
    end_date DATE,
    current_day INT DEFAULT 0,
    max_days INT DEFAULT 30,
    status TEXT DEFAULT 'upcoming', -- 'upcoming' | 'active' | 'completed'
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ─── COHORT VIDEOS (one per day per cohort) ─────────────────

CREATE TABLE IF NOT EXISTS cohort_videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cohort_id UUID REFERENCES cohorts(id) ON DELETE CASCADE,
    curriculum_day_id UUID REFERENCES curriculum_days(id) ON DELETE SET NULL,
    day_number INT NOT NULL,
    youtube_url TEXT,
    youtube_video_id TEXT,
    youtube_title TEXT,
    local_path TEXT,
    production_status TEXT DEFAULT 'pending',
    -- 'pending' | 'scripting' | 'rendering' | 'uploading' | 'ready' | 'failed'
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    aired_at TIMESTAMPTZ,
    UNIQUE(cohort_id, day_number)
);

-- ─── USERS (extended profile) ────────────────────────────────

CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT,
    avatar_url TEXT,
    cohort_id UUID REFERENCES cohorts(id) ON DELETE SET NULL,
    tier TEXT DEFAULT 'free',      -- 'free' | 'guided' | 'placement'
    onboarding_complete BOOLEAN DEFAULT FALSE,
    selected_topic_id UUID REFERENCES topics(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ─── DAILY PROGRESS ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    cohort_video_id UUID REFERENCES cohort_videos(id) ON DELETE CASCADE,
    day_number INT NOT NULL,
    video_watched BOOLEAN DEFAULT FALSE,
    practice_completed BOOLEAN DEFAULT FALSE,
    apply_completed BOOLEAN DEFAULT FALSE,
    deliverable_url TEXT,
    self_rating INT CHECK (self_rating >= 1 AND self_rating <= 5),
    notes TEXT,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, cohort_video_id)
);

-- ─── DELIVERABLES (user submissions) ─────────────────────────

CREATE TABLE IF NOT EXISTS deliverables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    day_number INT NOT NULL,
    type TEXT,                    -- 'blog' | 'code' | 'proposal' | 'screenshot' | 'other'
    title TEXT,
    content TEXT,
    file_url TEXT,
    rating INT CHECK (rating >= 1 AND rating <= 5),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ─── FUNNEL 2: FREELANCE PIPELINE ────────────────────────────

CREATE TABLE IF NOT EXISTS freelance_pipeline (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    stage TEXT DEFAULT 'exploring',
    -- 'exploring' | 'learning' | 'applying' | 'interviewing'
    -- | 'negotiating' | 'contracted' | 'delivering' | 'completed'
    started_learning_at TIMESTAMPTZ,
    completed_curriculum BOOLEAN DEFAULT FALSE,
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
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, topic)
);

CREATE TABLE IF NOT EXISTS contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    pipeline_id UUID REFERENCES freelance_pipeline(id) ON DELETE CASCADE,
    platform TEXT,                -- 'upwork' | 'fiverr' | 'contra' | 'direct'
    client_name TEXT,
    project_title TEXT,
    contract_value DECIMAL,
    your_rate DECIMAL,
    hours_worked INT,
    start_date DATE,
    end_date DATE,
    status TEXT DEFAULT 'active', -- 'active' | 'completed' | 'cancelled'
    payment_received BOOLEAN DEFAULT FALSE,
    client_review_given BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ─── TOPIC INTELLIGENCE (aggregated metrics) ─────────────────

CREATE TABLE IF NOT EXISTS topic_intelligence (
    topic TEXT PRIMARY KEY,
    freelance_job_count INT DEFAULT 0,
    avg_rate DECIMAL DEFAULT 0,
    demand_trend TEXT DEFAULT 'stable',
    total_enrolled INT DEFAULT 0,
    completion_rate DECIMAL DEFAULT 0,
    placement_rate DECIMAL DEFAULT 0,
    avg_days_to_first_contract INT,
    avg_first_contract_value DECIMAL,
    avg_earnings_90_days DECIMAL,
    viability_score DECIMAL DEFAULT 50,
    last_updated TIMESTAMPTZ DEFAULT now()
);

-- ─── VIDEO PRODUCTION LOG ────────────────────────────────────

CREATE TABLE IF NOT EXISTS video_production_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cohort_video_id UUID REFERENCES cohort_videos(id) ON DELETE CASCADE,
    step TEXT NOT NULL,           -- 'script' | 'panels' | 'tts' | 'render' | 'upload'
    status TEXT DEFAULT 'pending', -- 'pending' | 'running' | 'completed' | 'failed'
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_seconds INT,
    error_message TEXT,
    output_path TEXT
);

-- ─── INDEXES ─────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_progress_user_id ON user_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_freelance_pipeline_user_id ON freelance_pipeline(user_id);
CREATE INDEX IF NOT EXISTS idx_cohort_videos_cohort_id ON cohort_videos(cohort_id);
CREATE INDEX IF NOT EXISTS idx_cohorts_topic_id ON cohorts(topic_id);
CREATE INDEX IF NOT EXISTS idx_curriculum_days_curriculum ON curriculum_days(curriculum_id);
CREATE INDEX IF NOT EXISTS idx_deliverables_user_id ON deliverables(user_id);
CREATE INDEX IF NOT EXISTS idx_contracts_user_id ON contracts(user_id);
CREATE INDEX IF NOT EXISTS idx_user_acquisition_source ON user_acquisition(source);
