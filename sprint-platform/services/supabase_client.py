"""
Supabase client — real (service-role) when configured, in-memory FakeSupabase
in DEV mode. This is what lets `localhost` render the full mockup with no
database setup: when SUPABASE_URL is empty the store is seeded with demo data.
"""
import logging

from flask import current_app, g

from services.fake_supabase import FakeSupabase

logger = logging.getLogger(__name__)

_dev_db = None  # shared in-memory store for DEV mode + BDD tests
_live_client = None  # process-wide live client (create_client is expensive)


def is_live_configured(config=None):
    cfg = config if config is not None else (current_app.config if current_app else {})
    url = (cfg.get("SUPABASE_URL") or "").strip()
    key = (cfg.get("SUPABASE_SERVICE_KEY") or cfg.get("SUPABASE_KEY") or "").strip()
    return bool(url and key)


def get_supabase():
    """Return the Supabase client for the current request context."""
    if "supabase" in g:
        return g.supabase
    url = (current_app.config.get("SUPABASE_URL") or "").strip()
    key = (
        current_app.config.get("SUPABASE_SERVICE_KEY")
        or current_app.config.get("SUPABASE_KEY")
        or ""
    ).strip()
    if url and key:
        global _live_client
        if _live_client is None:
            from supabase import create_client
            _live_client = create_client(url, key)
            logger.info("Connected to live Supabase at %s", url)
        g.supabase = _live_client
        return g.supabase
    g.supabase = get_dev_db()
    return g.supabase


def get_dev_db():
    """Return (and lazily create) the shared in-memory store."""
    global _dev_db
    if _dev_db is None:
        _dev_db = FakeSupabase()
    return _dev_db


def reset_dev_db():
    """Clear the in-memory store. Used by BDD per-scenario isolation."""
    global _dev_db
    _dev_db = FakeSupabase()
