"""
Tests that contract form validation rejects invalid inputs.
Break: accepting negative values, empty names, or oversized strings.
"""
import pytest
from routes.contract import _validate_contract_form


def test_negative_contract_value_rejected():
    """Negative contract values corrupt earnings calculations."""
    errors = _validate_contract_form({
        "client_name": "Acme", "contract_value": "-100", "platform": "upwork",
    })
    assert "contract_value" in errors


def test_zero_contract_value_accepted():
    """Zero is valid (pro-bono work)."""
    errors = _validate_contract_form({
        "client_name": "Acme", "contract_value": "0", "platform": "upwork",
    })
    assert "contract_value" not in errors


def test_large_positive_value_accepted():
    """Large but reasonable values should be accepted."""
    errors = _validate_contract_form({
        "client_name": "Acme", "contract_value": "50000", "platform": "upwork",
    })
    assert "contract_value" not in errors


def test_unreasonably_large_value_rejected():
    """Values over 1M are likely data entry errors."""
    errors = _validate_contract_form({
        "client_name": "Acme", "contract_value": "99999999", "platform": "upwork",
    })
    assert "contract_value" in errors


def test_empty_client_name_rejected():
    """Ghost records with no client name are useless."""
    errors = _validate_contract_form({
        "client_name": "", "contract_value": "500", "platform": "upwork",
    })
    assert "client_name" in errors


def test_whitespace_only_client_name_rejected():
    """Whitespace-only names are effectively empty."""
    errors = _validate_contract_form({
        "client_name": "   ", "contract_value": "500", "platform": "upwork",
    })
    assert "client_name" in errors


def test_long_client_name_rejected():
    """Client names over 200 chars overflow the DB column."""
    errors = _validate_contract_form({
        "client_name": "A" * 201, "contract_value": "500", "platform": "upwork",
    })
    assert "client_name" in errors


def test_negative_hours_rejected():
    """Negative hours don't make sense."""
    errors = _validate_contract_form({
        "client_name": "Acme", "contract_value": "500", "hours_worked": "-5", "platform": "upwork",
    })
    assert "hours_worked" in errors


def test_valid_contract_accepted():
    """All valid inputs should produce no errors."""
    errors = _validate_contract_form({
        "client_name": "Acme Corp", "contract_value": "500",
        "your_rate": "50", "hours_worked": "10", "platform": "upwork",
    })
    assert len(errors) == 0, f"Valid form should have no errors, got: {errors}"
