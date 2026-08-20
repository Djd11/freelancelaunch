"""
outcome_service — sprint-owned outcome roll-ups (engineering-spec §4.3, arch §5.6).
contracts add/complete recompute total_earned, avg_contract_value, etc.
The sprint record is the single source of truth — no separate pipeline table.

Uses Supabase RPC functions (db/rpc.sql) for atomic operations:
  - add_contract_atomic: insert + rollup in one DB transaction
  - complete_contract_atomic: mark complete + bump counters in one transaction
Falls back to the multi-step Python approach if the RPCs are not deployed.
"""
import logging
import datetime

logger = logging.getLogger(__name__)


def _utcnow_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def add_contract(sb, sprint_id, user_id, **fields):
    """Insert a contract row and roll up the sprint outcome counters.
    Uses the add_contract_atomic RPC for a single-transaction guarantee;
    falls back to the multi-step approach if the RPC is not deployed."""
    try:
        res = sb.rpc("add_contract_atomic", {
            "p_sprint_id": sprint_id,
            "p_user_id": user_id,
            "p_client_name": fields.get("client_name"),
            "p_project_title": fields.get("project_title"),
            "p_contract_value": fields.get("contract_value", 0),
            "p_your_rate": fields.get("your_rate"),
            "p_hours_worked": fields.get("hours_worked"),
            "p_platform": fields.get("platform"),
            "p_status": fields.get("status", "active"),
            "p_is_repeat_client": fields.get("is_repeat_client", False),
        }).execute()
        return res.data[0] if res.data else None
    except Exception as exc:
        logger.warning("add_contract_atomic RPC failed, falling back to multi-step: %s", exc)
        return _add_contract_fallback(sb, sprint_id, user_id, **fields)


def _add_contract_fallback(sb, sprint_id, user_id, **fields):
    """Multi-step contract add (non-atomic fallback)."""
    res = sb.table("contracts").insert({
        "sprint_id": sprint_id,
        "user_id": user_id,
        "platform": fields.get("platform"),
        "client_name": fields.get("client_name"),
        "project_title": fields.get("project_title"),
        "contract_value": fields.get("contract_value", 0),
        "your_rate": fields.get("your_rate"),
        "hours_worked": fields.get("hours_worked"),
        "status": fields.get("status", "active"),
        "is_repeat_client": fields.get("is_repeat_client", False),
    }).execute()
    contract = res.data[0] if res.data else None

    sprint_rows = sb.table("sprints").select("contracts_won,total_earned,first_contract_at") \
        .eq("id", sprint_id).limit(1).execute().data
    if sprint_rows:
        s = sprint_rows[0]
        contracts_won = (s.get("contracts_won") or 0) + 1
        total = (s.get("total_earned") or 0) + (fields.get("contract_value") or 0)
        first_at = s.get("first_contract_at") or _utcnow_iso()
        avg = total / contracts_won if contracts_won else None
        sb.table("sprints").update({
            "contracts_won": contracts_won,
            "total_earned": total,
            "avg_contract_value": avg,
            "first_contract_at": first_at,
        }).eq("id", sprint_id).execute()
    return contract


def complete_contract(sb, sprint_id, contract_id):
    """Mark a contract completed and bump contracts_completed on the sprint.
    Uses the complete_contract_atomic RPC for a single-transaction guarantee;
    falls back to the multi-step approach if the RPC is not deployed."""
    try:
        res = sb.rpc("complete_contract_atomic", {
            "p_sprint_id": sprint_id,
            "p_contract_id": contract_id,
        }).execute()
        return res.data[0] if res.data else None
    except Exception as exc:
        logger.warning("complete_contract_atomic RPC failed, falling back to multi-step: %s", exc)
        return _complete_contract_fallback(sb, sprint_id, contract_id)


def _complete_contract_fallback(sb, sprint_id, contract_id):
    """Multi-step contract complete (non-atomic fallback)."""
    res = sb.table("contracts").update({"status": "completed"}) \
        .eq("id", contract_id).eq("sprint_id", sprint_id).execute()
    if not res.data:
        return None
    sprint_rows = sb.table("sprints").select("contracts_completed") \
        .eq("id", sprint_id).limit(1).execute().data
    if sprint_rows:
        completed = (sprint_rows[0].get("contracts_completed") or 0) + 1
        sb.table("sprints").update({"contracts_completed": completed}).eq("id", sprint_id).execute()
    return res.data[0]
