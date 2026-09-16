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

from flask import current_app, g, session
from supabase_auth import SyncSupportedStorage

logger = logging.getLogger(__name__)

# Session key holding the supabase-auth PKCE blob. Only the code verifier ever
# lands here (see FlaskSessionStorage docstring), and it is bound to the same
# signed, HttpOnly cookie as the rest of the session — which is exactly the
# CSRF binding PKCE wants: whoever holds the browser cookie holds the verifier.
PKCE_SESSION_KEY = "_sb_pkce"


class FlaskSessionStorage(SyncSupportedStorage):
    """supabase-auth storage backend persisted in ``flask.session``.

    Needed because the PKCE flow spans two requests: ``sign_in_with_oauth``
    generates the code verifier on the *start* request and
    ``exchange_code_for_session`` needs it back on the *callback* request. A
    process-wide memory store would leak verifiers between users (and break
    across Render's workers), so it goes in the caller's own session.

    The interface is an ABC at ``supabase_auth._sync.storage`` re-exported from
    the package root, and its methods are ``get_item`` / ``set_item`` /
    ``remove_item`` — NOT the ``get``/``set``/``delete`` a dict suggests
    (verified against supabase-auth 2.31.0:
    docs/superpowers/spikes/2026-09-15-t1-pkce-otp-spike.md §1).

    In practice this object only ever sees the key
    ``"supabase.auth.token-code-verifier"``: the client guards every session
    read/write behind ``persist_session``, which ``get_auth_supabase()`` turns
    off, so the session JSON stays in per-request memory and never touches here.
    """

    def get_item(self, key):
        bucket = session.get(PKCE_SESSION_KEY)
        if not isinstance(bucket, dict):
            return None
        return bucket.get(key)

    def set_item(self, key, value):
        # Reassign the whole sub-dict: mutating the nested dict in place leaves
        # ``session.modified`` False, and Flask 3.1 then skips Set-Cookie —
        # silently dropping the verifier and failing the callback with
        # "invalid flow state".
        bucket = dict(session.get(PKCE_SESSION_KEY) or {})
        bucket[key] = value
        session[PKCE_SESSION_KEY] = bucket
        session.modified = True

    def remove_item(self, key):
        bucket = dict(session.get(PKCE_SESSION_KEY) or {})
        if bucket.pop(key, None) is not None:
            session[PKCE_SESSION_KEY] = bucket
            session.modified = True


def _new_client(url, key, options=None):
    from supabase import create_client
    # `options` is positional-or-keyword here, and create_client is resolved at
    # call time on purpose: the test suite patches `supabase.create_client`,
    # which only takes effect while this import stays inside the function.
    return create_client(url, key, options) if options else create_client(url, key)


def _no_client_side_session():
    """ClientOptions with Supabase's own session machinery switched off.

    Applies to ALL three clients, not just the PKCE one. This is a
    server-rendered Flask app whose only auth authority is
    ``session["user_id"]`` (set by routes/auth.py and read by app.load_user);
    a Supabase ``Session`` object is never read back, so there is nothing for
    client-side persistence or token refresh to accomplish here.

    Leaving ``auto_refresh_token=True`` (the library default) is not inert:
    ``_save_session`` arms a **daemon ``threading.Timer``** for
    ``expires_in - 10s`` (~55 min at a 1 h TTL). Measured on supabase-auth
    2.31.0 — armed with the defaults, and with a near-term expiry it really fired
    at 1.84 s. ``persist_session`` does *not* gate the arming; only
    ``auto_refresh_token`` does. Since these clients are request-scoped, that
    timer outlives ``close_request_clients()`` and then calls the refresh
    endpoint on an httpx session that teardown already closed — and because
    ``refresh_token_function`` catches everything and retries only
    ``AuthRetryableError``, a closed-client ``RuntimeError`` is swallowed in
    silence, so the failure never reaches a log. Net cost per login: a whole
    client plus a valid refresh token pinned in the timer's closure for an hour,
    and a refresh that can never succeed. Killing it removes the thread, the
    retention and the post-teardown path in one line.

    No behavioural risk to RLS: ``create_client`` reads ``auth.get_session()``
    once at construction to build the Authorization header, and a fresh
    request-scoped client has no stored session either way — so both clients keep
    sending the apikey header exactly as before (anon for RLS-scoped reads,
    service-role only for admin workers).

    A fresh ``ClientOptions`` (and so a fresh ``SyncMemoryStorage``) is built per
    call — never hoist it to a module constant, or the clients would share one
    storage instance.
    """
    from supabase import ClientOptions
    return ClientOptions(persist_session=False, auto_refresh_token=False)


def close_request_clients(_exc=None):
    """Close any per-request Supabase sessions (registered as app teardown)."""
    for attr in ("supabase", "client_supabase", "auth_supabase"):
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
    client = _new_client(url, key, _no_client_side_session())
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
    # Accept both spellings, mirroring the service-role pair above: Config only
    # publishes `SUPABASE_KEY` (it reads env SUPABASE_ANON_KEY into it), so
    # looking up `SUPABASE_ANON_KEY` alone always came back empty and this
    # function raised even on a fully configured project.
    key = (current_app.config.get("SUPABASE_ANON_KEY")
           or current_app.config.get("SUPABASE_KEY") or "").strip()
    if not (url and key):
        raise RuntimeError(
            "Supabase anon key is not configured. Set SUPABASE_ANON_KEY "
            "in the environment (copy .env.example to .env)."
        )
    client = _new_client(url, key, _no_client_side_session())
    g.client_supabase = client
    return client


def get_auth_supabase():
    """Return the request-scoped ANON client configured for the PKCE auth flow.

    This is the client the OTP and OAuth routes must use (design §5.1): it runs
    as the browser would, so RLS applies, and unlike the two clients above it is
    built with ``flow_type="pkce"`` plus a session-backed storage so the code
    verifier survives the provider round-trip.

    ``persist_session=False`` / ``auto_refresh_token=False`` are deliberate and
    load-bearing: this app's session contract is ``session["user_id"]`` only, so
    a Supabase Session must never be written into the cookie (it would carry a
    refresh token the server has no use for), and a background refresh timer
    would keep touching an httpx client that teardown already closed.
    """
    if "auth_supabase" in g:
        return g.auth_supabase
    url = (current_app.config.get("SUPABASE_URL") or "").strip()
    key = (current_app.config.get("SUPABASE_ANON_KEY")
           or current_app.config.get("SUPABASE_KEY") or "").strip()
    if not (url and key):
        raise RuntimeError(
            "Supabase anon key is not configured, so the passwordless sign-in "
            "flow cannot run. Set SUPABASE_URL and SUPABASE_ANON_KEY in the "
            "environment (copy .env.example to .env — see "
            "docs/supabase-setup.md)."
        )
    # `supabase.ClientOptions` IS `SyncClientOptions` (the package exports only
    # the former name; importing SyncClientOptions raises AttributeError).
    from supabase import ClientOptions

    options = ClientOptions(
        flow_type="pkce",
        storage=FlaskSessionStorage(),
        persist_session=False,
        auto_refresh_token=False,
    )
    client = _new_client(url, key, options)
    g.auth_supabase = client
    return client


def reset_clients():
    """No-op kept for test compatibility — clients are request-scoped now."""
    pass
