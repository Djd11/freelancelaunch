"""
outcome_service — sprint-owned outcome roll-ups (engineering-spec §4.3, arch §5.6).
contracts add/complete recompute total_earned, avg_contract_value, etc.
The sprint record is the single source of truth — no separate pipeline table.
"""
import datetime


def _utcnow_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def add_contract(sb, sprint_id, user_id, **fields):
    """Insert a contract row and roll up the sprint outcome counters."""
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
        # First contract stamps a real timestamp (never a string literal).
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
    """Mark a contract completed and bump contracts_completed on the sprint."""
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
