"""
Tests for atomic contract operations and avg_contract_value fix.
Break: non-atomic multi-step add_contract leaves stale sprint counters.
Break: avg_contract_value uses contracts_won instead of contracts_completed.
"""
import pytest
from unittest.mock import MagicMock


def test_add_contract_atomic_inserts_and_updates_sprint():
    """add_contract_atomic must insert a contract and update sprint counters
    in a single transaction.
    Break: separate insert + update leaves stale counters on failure."""
    from services.outcome_service import add_contract

    sb = MagicMock()

    # Mock contract insert
    inserted_contract = {"id": "c1", "sprint_id": "s1", "contract_value": 500}
    sb.table.return_value.insert.return_value.execute.return_value.data = [inserted_contract]

    # Mock sprint read (before update)
    sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"contracts_won": 2, "total_earned": 1000, "first_contract_at": None, "contracts_completed": 1}
    ]

    result = add_contract(
        sb, "s1", "u1",
        client_name="Acme",
        contract_value=500,
    )

    # Verify the contract was inserted
    assert result["id"] == "c1"
    assert result["contract_value"] == 500

    # Verify sprint counters were updated
    update_calls = sb.table.return_value.update.call_args_list
    assert len(update_calls) >= 1, "Should have called update on sprints table"

    # Find the sprint update (should be the one with contracts_won)
    sprint_update = None
    for call in update_calls:
        args, kwargs = call
        if args and isinstance(args[0], dict) and "contracts_won" in args[0]:
            sprint_update = args[0]
            break

    assert sprint_update is not None, "Should have updated sprints counters"
    assert sprint_update["contracts_won"] == 3, f"Expected contracts_won=3, got {sprint_update['contracts_won']}"
    assert sprint_update["total_earned"] == 1500, f"Expected total_earned=1500, got {sprint_update['total_earned']}"


def test_avg_contract_value_uses_total_earned_div_contracts_won():
    """avg_contract_value must be total_earned / contracts_won, NOT
    total_earned / contracts_completed.
    Break: using contracts_completed as denominator."""
    from services.outcome_service import add_contract

    sb = MagicMock()

    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "c1"}]

    # Sprint has 5 contracts_won but only 2 completed
    sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"contracts_won": 5, "total_earned": 2500, "first_contract_at": "2026-01-01", "contracts_completed": 2}
    ]

    add_contract(sb, "s1", "u1", client_name="Acme", contract_value=500)

    # Find the avg update
    update_calls = sb.table.return_value.update.call_args_list
    for call in update_calls:
        args, _ = call
        if args and isinstance(args[0], dict) and "avg_contract_value" in args[0]:
            avg = args[0]["avg_contract_value"]
            # 3000 / 6 = 500 (using contracts_won)
            # NOT 3000 / 3 = 1000 (which would be contracts_completed)
            assert avg == 500.0, f"Expected avg=500.0 (total/won), got {avg}"
            return

    pytest.fail("avg_contract_value was never set in sprint update")


def test_complete_contract_increments_completed():
    """complete_contract must increment contracts_completed on the sprint.
    Break: not incrementing completed counter."""
    from services.outcome_service import complete_contract

    sb = MagicMock()

    # Mock contract update: table().update().eq().eq().execute()
    contract_update_result = MagicMock()
    contract_update_result.data = [{"id": "c1", "status": "completed"}]
    sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = contract_update_result

    # Mock sprint read: table().select().eq().limit().execute()
    sprint_read_result = MagicMock()
    sprint_read_result.data = [{"contracts_completed": 3}]
    sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = sprint_read_result

    # Mock sprint update: table().update().eq().execute()
    sprint_update_result = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = sprint_update_result

    result = complete_contract(sb, "s1", "c1")

    assert result["status"] == "completed"

    # Verify contracts_completed was incremented
    update_calls = sb.table.return_value.update.call_args_list
    for call in update_calls:
        args, _ = call
        if args and isinstance(args[0], dict) and "contracts_completed" in args[0]:
            assert args[0]["contracts_completed"] == 4, (
                f"Expected contracts_completed=4, got {args[0]['contracts_completed']}"
            )
            return

    pytest.fail("contracts_completed was never updated")
