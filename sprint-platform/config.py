"""
Sprint Platform — Configuration.
The app talks to a single dedicated Supabase project: SUPABASE_URL plus the
service-role key (SUPABASE_SERVICE_ROLE_KEY, or SUPABASE_SERVICE_KEY as set on
Render) are required — see .env.example and docs/supabase-setup.md. There is no
in-memory fallback database.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "sprint-dev-secret-change-in-production")

    # Session cookie hardening: on the https deployment the cookie must never
    # travel over plain HTTP (Render terminates TLS at its proxy; ProxyFix in
    # app.py makes request.scheme honest).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = (os.getenv("PUBLIC_BASE_URL", "").startswith("https://")
                             or os.getenv("FLASK_ENV") == "production")

    # Supabase (new, dedicated project only — see docs/supabase-setup.md).
    # Accept both spellings of the privileged key: local .env uses
    # SUPABASE_SERVICE_ROLE_KEY, the Render service was created with
    # SUPABASE_SERVICE_KEY. Without the fallback the app would silently drop to
    # the anon key and every service-role read would come back empty under RLS.
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", os.getenv("SUPABASE_KEY", ""))
    SUPABASE_SERVICE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                            or os.getenv("SUPABASE_SERVICE_KEY", ""))

    # LLM fallback chain (optional — app works without these)
    LLM_API_URL = os.getenv("LLM_API_URL", "")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

    # Admin (email match)
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

    # Cohort defaults
    DEFAULT_COHORT_DAYS = 14
