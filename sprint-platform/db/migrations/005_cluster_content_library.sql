-- =====================================================================
-- 005 — CLUSTER CONTENT LIBRARY (run in Supabase SQL Editor, idempotent)
-- Admin provisions the 14-day course content ONCE per job cluster; every
-- learner enrolling in that cluster consumes it with zero per-user LLM
-- calls (arch §2 principle 3: cohort amortization).
-- Also mirrored in db/schema.sql.
--
-- Sentinel columns: day rows carry project_index=0; project rows carry
-- day_no=0. All four unique-key columns are NOT NULL so PostgREST upserts
-- (on_conflict="cluster_key,kind,day_no,project_index") conflict correctly —
-- NULLs are distinct in Postgres unique constraints and would duplicate rows.
-- =====================================================================

CREATE TABLE IF NOT EXISTS cluster_content_library (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_key TEXT NOT NULL REFERENCES job_clusters(cluster_key) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('day', 'project')),

    -- kind='day' → day_no 1..14, project_index 0.
    -- kind='project' → project_index 1..3, day_no 0.
    day_no INT NOT NULL DEFAULT 0,
    project_index INT NOT NULL DEFAULT 0,
    CHECK (
      (kind = 'day' AND day_no BETWEEN 1 AND 14 AND project_index = 0)
      OR
      (kind = 'project' AND project_index BETWEEN 1 AND 3 AND day_no = 0)
    ),

    -- kind='day' → the lesson JSON the day view stores in
    -- sprint_days.action_payload.lesson (title/objective/script/key_points/
    -- pitfalls/quiz/quiz_answers/hook/day_overview/usefulness_context/
    -- pre_quiz/voiceover). kind='project' → the anatomy (title/clone_steps/
    -- rubric/reference_spec/gap_fill_topic).
    content JSONB NOT NULL DEFAULT '{}',

    -- 'generated' = produced by the LLM worker under admin control;
    -- 'edited'    = admin overrode via the content editor. Regeneration
    --               never clobbers 'edited' rows (force only rewrites
    --               'generated' ones).
    origin TEXT NOT NULL DEFAULT 'generated' CHECK (origin IN ('generated','edited')),

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (cluster_key, kind, day_no, project_index)
);
CREATE INDEX IF NOT EXISTS idx_content_library_cluster
    ON cluster_content_library(cluster_key, kind);
