"""
Supabase client singleton
"""
from flask import current_app, g
from supabase import create_client, Client

def get_supabase() -> Client:
    """Get or create a Supabase client for the current request context.
    Uses service_role key to bypass RLS for MVP. Add proper RLS policies later."""
    if "supabase" not in g:
        url = current_app.config["SUPABASE_URL"]
        key = current_app.config["SUPABASE_SERVICE_KEY"] or current_app.config["SUPABASE_KEY"]
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
        g.supabase = create_client(url, key)
    return g.supabase

def get_supabase_service() -> Client:
    """Get a Supabase client with service_role key (bypasses RLS)."""
    url = current_app.config["SUPABASE_URL"]
    key = current_app.config["SUPABASE_SERVICE_KEY"] or current_app.config["SUPABASE_KEY"]
    return create_client(url, key)
