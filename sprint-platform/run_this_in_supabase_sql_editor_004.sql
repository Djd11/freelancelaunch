-- db/migrations/004_gate_b_content.sql
-- Content-quality fix P0-2: Gate B (Mock Contract → Phase C) becomes
-- content-aware, not just valid-URL + case-study-presence.
-- Run this in Supabase SQL Editor (repo convention: db/migrations/*.sql).
-- The column stores parsed rubric artifacts / self-check flags from the
-- submitted deliverable, written by verification_service.auto_check_gate_b.

ALTER TABLE verification_reviews ADD COLUMN IF NOT EXISTS gate_b_evidence JSONB;

-- Optional: verify
-- SELECT column_name, data_type FROM information_schema.columns
-- WHERE table_name = 'verification_reviews' AND column_name = 'gate_b_evidence';
