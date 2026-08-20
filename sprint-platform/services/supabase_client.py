"""
Supabase client — dual-key: anon for routes (RLS enforced), service-role for
admin workers (arch §4.4, fix: anon vs service key split).

Routes use get_client_supabase() (anon key → RLS policies apply).
Background workers use get_supabase() (service role → bypasses RLS).
"""
import logging

from flask import current_app, g

logger = logging.getLogger(__name__)

_live_client = None          # process-wide service-role client
_client_supabase_client = None  # process-wide anon-key client


def get_supabase():
    """Return the service-role Supabase client (admin workers only).

    Bypasses RLS — use only for server-side admin operations.
    Raises RuntimeError when the project is not configured.
    """
    if "supabase" in g:
        return g.supabase
    url = (current_app.config.get("SUPABASE_URL") or "").strip()
    key = (
        current_app.config.get("SUPABASE_SERVICE_KEY")
        or current_app.config.get("SUPABASE_KEY")
        or ""
    ).strip()
    if not (url and key):
        raise RuntimeError(
            "Supabase is not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY in the environment (copy .env.example "
            "to .env — see docs/supabase-setup.md)."
        )
    global _live_client
    if _live_client is None:
        from supabase import create_client
        _live_client = create_client(url, key)
        logger.info("Connected to live Supabase at %s (service role)", url)
    g.supabase = _live_client
    return g.supabase


def get_client_supabase():
    """Return the anon-key Supabase client for request-scoped reads/writes.

    Uses RLS policies — never the service-role key. This is the client
    that routes should use for all user-facing operations.
    Raises RuntimeError when the anon key is not configured.
    """
    if "client_supabase" in g:
        return g.client_supabase
    url = (current_app.config.get("SUPABASE_URL") or "").strip()
    key = (current_app.config.get("SUPABASE_ANON_KEY") or "").strip()
    if not (url and key):
        raise RuntimeError(
            "Supabase anon key is not configured. Set SUPABASE_ANON_KEY "
            "in the environment (copy .env.example to .env)."
        )
    global _client_supabase_client
    if _client_supabase_client is None:
        from supabase import create_client
        _client_supabase_client = create_client(url, key)
        logger.info("Connected to live Supabase at %s (anon key)", url)
    g.client_supabase = _client_supabase_client
    return g.client_supabase


def reset_clients():
    """Reset all cached clients (for tests)."""
    global _live_client, _client_supabase_client
    _live_client = None
    _client_supabase_client = None
