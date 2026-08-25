-- db/migrations/003_copywork_reference_spec.sql
-- Content-quality fix P0-2: generated reference build specs replace
-- placeholder source URLs. Run in the Supabase SQL Editor to deploy
-- (repo convention — see db/rpc.sql header).

-- The LLM-generated screen-by-screen breakdown of the build the learner
-- replicates. Written by lesson_engine._store_reference_spec.
ALTER TABLE copywork_projects ADD COLUMN IF NOT EXISTS reference_spec TEXT;

-- Seeded skeletons no longer ship any external URL (source_url="" today);
-- allow NULL so post-migration writes can omit it entirely.
ALTER TABLE copywork_projects ALTER COLUMN source_url DROP NOT NULL;
