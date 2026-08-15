"""
Sprint Platform — Configuration.
The app talks to the dedicated Supabase project: SUPABASE_URL +
SUPABASE_SERVICE_ROLE_KEY are required (see .env.example and
docs/supabase-setup.md). There is no in-memory fallback database.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "sprint-dev-secret-change-in-production")

    # Supabase (new, dedicated project only — see docs/supabase-setup.md)
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", os.getenv("SUPABASE_KEY", ""))
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # LLM fallback chain (optional — app works without these)
    LLM_API_URL = os.getenv("LLM_API_URL", "")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

    # Admin (email match)
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

    # Cohort defaults
    DEFAULT_COHORT_DAYS = 14
