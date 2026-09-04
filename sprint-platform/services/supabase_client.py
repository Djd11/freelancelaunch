"""
Supabase client — dual-key: anon for routes (RLS enforced), service-role for
admin workers (arch §4.4, fix: anon vs service key split).

Routes use get_client_supabase() (anon key → RLS policies apply).
Background workers use get_supabase() (service role → bypasses RLS).

Clients are REQUEST-SCOPED (cached on `g`, created fresh per request/app
context). A process-wide shared client was the root cause of the dogfood
concurrency 500s: its long-lived HTTP/2 connection goes stale when the
Supabase edge closes an idle socket, and concurrent writes to the dead
connection raise httpx.WriteError, which postgrest does not retry. One
client per request = one fresh TLS connection, shared by that request's
queries and closed at teardown — no cross-thread socket sharing.
"""
import logging

from flask import current_app, g

logger = logging.getLogger(__name__)


def _new_client(url, key):
    from supabase import create_client
    return create_client(url, key)


def close_request_clients(_exc=None):
    """Close any per-request Supabase sessions (registered as app teardown)."""
    for attr in ("supabase", "client_supabase"):
        client = g.pop(attr, None)
        if client is None:
            continue
        for holder in (getattr(client, "postgrest", None),
                       getattr(client, "storage", None)):
            session = getattr(holder, "session", None) if holder else None
            try:
                if session is not None:
                    session.close()
            except Exception:
                pass
        auth = getattr(client, "auth", None)
        http_client = getattr(auth, "_http_client", None) if auth else None
        try:
            if http_client is not None:
                http_client.close()
        except Exception:
            pass


def get_supabase():
    """Return the service-role Supabase client for this request/context.

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
    client = _new_client(url, key)
    g.supabase = client
    return client


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
    client = _new_client(url, key)
    g.client_supabase = client
    return client


def reset_clients():
    """No-op kept for test compatibility — clients are request-scoped now."""
    pass
