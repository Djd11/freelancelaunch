"""
Supabase client — live service-role client only (architecture.md §4.4).

The app has exactly one data layer: the dedicated Supabase project configured
via SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (see .env.example and
docs/supabase-setup.md). There is no in-memory/dev-mode database.
"""
import logging

from flask import current_app, g

logger = logging.getLogger(__name__)

_live_client = None  # process-wide live client (create_client is expensive)


def get_supabase():
    """Return the live Supabase client for the current request context.

    Raises RuntimeError when the project is not configured — the app has no
    fallback data layer, so a missing configuration must fail loudly instead
    of silently serving an empty store.
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
        logger.info("Connected to live Supabase at %s", url)
    g.supabase = _live_client
    return g.supabase
