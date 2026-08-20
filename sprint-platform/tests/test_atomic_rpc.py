"""
Tests for atomic contract operations and avg_contract_value fix.
Break: non-atomic multi-step add_contract leaves stale sprint counters.
Break: avg_contract_value uses contracts_won instead of contracts_completed.
"""
import pytest
from unittest.mock import MagicMock


def test_add_contract_uses_rpc_when_available():
    """add_contract must call the RPC function when it's deployed.
    Break: always using the multi-step fallback even when RPC exists."""
    from services.outcome_service import add_contract

    sb = MagicMock()
    rpc_result = MagicMock()
    rpc_result.execute.return_value.data = [{"id": "c1", "sprint_id": "s1", "contract_value": 500}]
    sb.rpc.return_value = rpc_result

    result = add_contract(sb, "s1", "u1", client_name="Acme", contract_value=500)

    sb.rpc.assert_called_once_with("add_contract_atomic", {
        "p_sprint_id": "s1",
        "p_user_id": "u1",
        "p_client_name": "Acme",
        "p_project_title": None,
        "p_contract_value": 500,
        "p_your_rate": None,
        "p_hours_worked": None,
        "p_platform": None,
        "p_status": "active",
        "p_is_repeat_client": False,
    })
    assert result["id"] == "c1"
    assert result["contract_value"] == 500


def test_add_contract_falls_back_when_rpc_fails():
    """add_contract must fall back to multi-step when the RPC doesn't exist.
    Break: crashing when add_contract_atomic is not deployed."""
    from services.outcome_service import add_contract

    sb = MagicMock()
    sb.rpc.side_effect = Exception("function add_contract_atomic() does not exist")

    # Mock the fallback path: insert → select → update
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "c1"}]
    sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"contracts_won": 2, "total_earned": 1000, "first_contract_at": None}
    ]

    result = add_contract(sb, "s1", "u1", client_name="Acme", contract_value=500)

    # Verify fallback ran (table calls happened)
    sb.table.assert_called()
    assert result["id"] == "c1"


def test_avg_contract_value_uses_contracts_won_denominator():
    """avg_contract_value must be total_earned / contracts_won, NOT
    total_earned / contracts_completed.
    Break: using contracts_completed as denominator."""
    from services.outcome_service import add_contract

    sb = MagicMock()
    sb.rpc.side_effect = Exception("not deployed")

    # Fallback path: sprint has 5 contracts_won but only 2 completed
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "c1"}]
    sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"contracts_won": 5, "total_earned": 2500, "first_contract_at": "2026-01-01", "contracts_completed": 2}
    ]

    add_contract(sb, "s1", "u1", client_name="Acme", contract_value=500)

    # Find the avg update in the fallback path
    update_calls = sb.table.return_value.update.call_args_list
    for call in update_calls:
        args, _ = call
        if args and isinstance(args[0], dict) and "avg_contract_value" in args[0]:
            avg = args[0]["avg_contract_value"]
            # 3000 / 6 = 500 (using contracts_won)
            assert avg == 500.0, f"Expected avg=500.0 (total/won), got {avg}"
            return

    pytest.fail("avg_contract_value was never set in sprint update")


def test_complete_contract_uses_rpc_when_available():
    """complete_contract must call the RPC function when it's deployed.
    Break: always using the multi-step fallback even when RPC exists."""
    from services.outcome_service import complete_contract

    sb = MagicMock()
    rpc_result = MagicMock()
    rpc_result.execute.return_value.data = [{"id": "c1", "status": "completed"}]
    sb.rpc.return_value = rpc_result

    result = complete_contract(sb, "s1", "c1")

    sb.rpc.assert_called_once_with("complete_contract_atomic", {
        "p_sprint_id": "s1",
        "p_contract_id": "c1",
    })
    assert result["status"] == "completed"


def test_complete_contract_falls_back_when_rpc_fails():
    """complete_contract must fall back to multi-step when the RPC doesn't exist.
    Break: crashing when complete_contract_atomic is not deployed."""
    from services.outcome_service import complete_contract

    sb = MagicMock()
    sb.rpc.side_effect = Exception("function complete_contract_atomic() does not exist")

    # Mock fallback path: update contract → read sprint → update sprint
    contract_update = MagicMock()
    contract_update.data = [{"id": "c1", "status": "completed"}]
    sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = contract_update

    sprint_read = MagicMock()
    sprint_read.data = [{"contracts_completed": 3}]
    sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = sprint_read

    sprint_update = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = sprint_update

    result = complete_contract(sb, "s1", "c1")

    assert result["status"] == "completed"
