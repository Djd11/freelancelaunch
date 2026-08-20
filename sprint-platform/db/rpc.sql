-- db/rpc.sql
-- Transactional RPC functions for the sprint platform.
-- Run this in the Supabase SQL Editor to deploy.

-- 1. Atomic contract add + sprint counter rollup
-- Replaces the non-atomic multi-step add_contract in outcome_service.py.
-- Uses a single DB transaction: insert contract → update sprint counters.
CREATE OR REPLACE FUNCTION add_contract_atomic(
    p_sprint_id UUID,
    p_user_id UUID,
    p_client_name TEXT,
    p_project_title TEXT,
    p_contract_value NUMERIC,
    p_your_rate NUMERIC,
    p_hours_worked INTEGER,
    p_platform TEXT,
    p_status TEXT DEFAULT 'active',
    p_is_repeat_client BOOLEAN DEFAULT FALSE
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_contract JSONB;
    v_sprint RECORD;
    v_contracts_won INTEGER;
    v_total NUMERIC;
    v_first_at TIMESTAMPTZ;
    v_avg NUMERIC;
BEGIN
    -- 1. Insert the contract row
    INSERT INTO contracts (
        sprint_id, user_id, client_name, project_title,
        contract_value, your_rate, hours_worked,
        platform, status, is_repeat_client
    ) VALUES (
        p_sprint_id, p_user_id, p_client_name, p_project_title,
        p_contract_value, p_your_rate, p_hours_worked,
        p_platform, p_status, p_is_repeat_client
    )
    RETURNING to_jsonb(contracts.*) INTO v_contract;

    -- 2. Read current sprint counters (FOR UPDATE to prevent race)
    SELECT contracts_won, total_earned, first_contract_at, contracts_completed
    INTO v_sprint
    FROM sprints
    WHERE id = p_sprint_id
    FOR UPDATE;

    -- 3. Compute new counters atomically
    v_contracts_won := COALESCE(v_sprint.contracts_won, 0) + 1;
    v_total := COALESCE(v_sprint.total_earned, 0) + COALESCE(p_contract_value, 0);
    v_first_at := COALESCE(v_sprint.first_contract_at, now());
    -- avg uses contracts_won as denominator (not contracts_completed)
    v_avg := CASE WHEN v_contracts_won > 0 THEN v_total / v_contracts_won ELSE NULL END;

    -- 4. Update sprint counters in the same transaction
    UPDATE sprints SET
        contracts_won = v_contracts_won,
        total_earned = v_total,
        avg_contract_value = v_avg,
        first_contract_at = v_first_at
    WHERE id = p_sprint_id;

    RETURN v_contract;
END;
$$;


-- 2. Atomic contract complete + sprint counter rollup
-- Replaces the non-atomic complete_contract in outcome_service.py.
CREATE OR REPLACE FUNCTION complete_contract_atomic(
    p_sprint_id UUID,
    p_contract_id UUID
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_contract JSONB;
    v_sprint RECORD;
    v_completed INTEGER;
    v_total_for_avg NUMERIC;
    v_won INTEGER;
    v_avg NUMERIC;
BEGIN
    -- 1. Mark contract as completed
    UPDATE contracts
    SET status = 'completed'
    WHERE id = p_contract_id AND sprint_id = p_sprint_id
    RETURNING to_jsonb(contracts.*) INTO v_contract;

    IF v_contract IS NULL THEN
        RAISE EXCEPTION 'Contract % not found in sprint %', p_contract_id, p_sprint_id;
    END IF;

    -- 2. Read sprint counters (FOR UPDATE)
    SELECT contracts_won, contracts_completed, total_earned
    INTO v_sprint
    FROM sprints
    WHERE id = p_sprint_id
    FOR UPDATE;

    -- 3. Bump contracts_completed
    v_completed := COALESCE(v_sprint.contracts_completed, 0) + 1;

    -- 4. Recompute avg using contracts_won as denominator
    v_won := COALESCE(v_sprint.contracts_won, 0);
    v_total_for_avg := COALESCE(v_sprint.total_earned, 0);
    v_avg := CASE WHEN v_won > 0 THEN v_total_for_avg / v_won ELSE NULL END;

    -- 5. Update sprint
    UPDATE sprints SET
        contracts_completed = v_completed,
        avg_contract_value = v_avg
    WHERE id = p_sprint_id;

    RETURN v_contract;
END;
$$;


-- 3. Partial unique index for cohort race prevention
-- Only one active cohort per cluster_key is allowed.
CREATE UNIQUE INDEX IF NOT EXISTS idx_cohorts_active_per_cluster
    ON cohorts (cluster_key) WHERE status = 'active';
