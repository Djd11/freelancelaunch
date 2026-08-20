"""
Tests that the anon-key client is used for routes (RLS enforced)
and the service-key client is used for admin workers (breaks RLS).
"""
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["SUPABASE_URL"] = "https://test.supabase.co"
    app.config["SUPABASE_ANON_KEY"] = "anon-key-123"
    app.config["SUPABASE_SERVICE_KEY"] = "service-key-456"
    return app


def test_client_uses_anon_key_not_service_key(app):
    """The route-facing client must use the anon key so RLS is enforced.
    Break: returning the service-role key to routes."""
    from services.supabase_client import get_client_supabase, reset_clients
    reset_clients()
    with app.app_context():
        with patch("supabase.create_client") as mock_create:
            mock_create.return_value = MagicMock(name="anon_client")
            client = get_client_supabase()
            call_args = mock_create.call_args[0]
            assert call_args[1] == "anon-key-123", (
                f"Expected anon key 'anon-key-123', got '{call_args[1]}'"
            )
            assert call_args[1] != "service-key-456", "Must NOT use the service-role key"


def test_service_client_uses_service_key(app):
    """The admin worker client must use the service-role key for background tasks."""
    from services.supabase_client import get_supabase, reset_clients
    reset_clients()
    with app.app_context():
        with patch("supabase.create_client") as mock_create:
            mock_create.return_value = MagicMock(name="service_client")
            client = get_supabase()
            call_args = mock_create.call_args[0]
            assert call_args[1] == "service-key-456", (
                f"Expected service key 'service-key-456', got '{call_args[1]}'"
            )


def test_missing_anon_key_raises_runtime_error(app):
    """A missing anon key must fail loudly — never silently fall back to service key."""
    from services.supabase_client import get_client_supabase, reset_clients
    reset_clients()
    app.config["SUPABASE_ANON_KEY"] = ""
    with app.app_context():
        with pytest.raises(RuntimeError, match="not configured"):
            get_client_supabase()


def test_same_client_returned_within_request(app):
    """Multiple calls within one request must return the same cached instance."""
    from services.supabase_client import get_client_supabase, reset_clients
    reset_clients()
    with app.app_context():
        with patch("supabase.create_client") as mock_create:
            mock_create.return_value = MagicMock(name="anon_client")
            c1 = get_client_supabase()
            c2 = get_client_supabase()
            assert c1 is c2
            assert mock_create.call_count == 1, "create_client should be called once per request"
