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

# Providers this app knows how to render a button for, and the only ones the
# Supabase dashboard checklist (design §6) can enable on the $0 stack. A name
# outside this tuple is dropped from OAUTH_PROVIDERS rather than passed on to
# supabase-auth, so a typo in the env var can never produce a dead button.
OAUTH_PROVIDER_ALLOW_LIST = ("google", "facebook", "twitter")


def _env_bool(name, default="false"):
    """Parse a boolean env var: 1/true/yes/on in any case are True.

    An unset *or blank* value takes `default` (a half-filled .env must not
    silently disable the feature); any other unrecognised value is False, so a
    typo like "ture" fails closed instead of turning the flow on.
    """
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default.strip().lower() in ("1", "true", "yes", "on")
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _oauth_providers():
    """Validated lowercase set of enabled social providers (design §5.3).

    FB is appended only once Meta app review passes (§6.3) — the code path is
    identical, so flipping this env var is the whole rollout.
    """
    raw = os.getenv("OAUTH_PROVIDERS", ",".join(OAUTH_PROVIDER_ALLOW_LIST))
    wanted = {p.strip().lower() for p in raw.split(",") if p.strip()}
    return {p for p in wanted if p in OAUTH_PROVIDER_ALLOW_LIST}


_PUBLIC_BASE = (os.getenv("PUBLIC_BASE_URL") or "http://localhost:5000").rstrip("/")


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

    # ── Passwordless auth (email OTP + social OAuth) — design §5.3 ─────────
    # The OTP and OAuth paths talk to Supabase Auth with the ANON key above;
    # no new secrets are introduced. Provider enablement, SMTP and the email
    # template all live in the Supabase dashboard (design §6).
    OTP_EMAIL_ENABLED = _env_bool("OTP_EMAIL_ENABLED", "true")
    OAUTH_PROVIDERS = _oauth_providers()

    # Canonical origin for the OAuth `redirect_to` we hand Supabase. Must match
    # an entry in dashboard → Auth → URL Configuration → Additional redirect
    # URLs, or the callback is rejected. Defaults to the local dev origin.
    PUBLIC_BASE_URL = _PUBLIC_BASE
    OAUTH_REDIRECT_BASE = _PUBLIC_BASE

    # Deployment guard inputs (see app.create_app). The base above has a DEV
    # default, so "did the operator actually set it?" cannot be recovered from
    # the value alone — record the provenance explicitly. Without this, a
    # production deploy with PUBLIC_BASE_URL cleared would quietly hand Supabase
    # an http://localhost:5000 redirect_to: every social sign-in ends on the
    # operator's own machine, and the user-visible symptom ("Social sign-in
    # didn't complete") looks exactly like a Supabase or Google outage.
    FLASK_ENV = (os.getenv("FLASK_ENV") or "").strip().lower()
    PUBLIC_BASE_URL_SET = bool((os.getenv("PUBLIC_BASE_URL") or "").strip())
    OAUTH_CALLBACK_PATH = "/auth/oauth/callback"

    # Server-side resend throttle (design §5.2). Tests lower this to avoid
    # sleeping; Supabase dashboard rate limits + the SMTP free-tier cap are the
    # outer belts, this is the inner one.
    OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "60"))
    # Mirrors dashboard → Auth → "One-time password" length. Measured on this
    # project on 2026-09-15: 8 digits (the design said 6 — see
    # docs/superpowers/spikes/2026-09-15-t1-pkce-otp-spike.md §4). Drives the
    # code-entry input's maxlength, not any validation.
    OTP_CODE_LENGTH = int(os.getenv("OTP_CODE_LENGTH", "8"))


    # LLM fallback chain (optional — app works without these)
    LLM_API_URL = os.getenv("LLM_API_URL", "")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

    # Admin (email match)
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

    # Cohort defaults
    DEFAULT_COHORT_DAYS = 14
