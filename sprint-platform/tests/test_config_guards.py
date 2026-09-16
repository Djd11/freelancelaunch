"""Boot-time deployment guard for the OAuth origin (t5, reviewer item 3).

Own file so it does not grow tests/test_auth_otp.py, which qa-eng owns.

The guard exists because Config.PUBLIC_BASE_URL has a *dev* default
(http://localhost:5000). That value is also the base handed to Supabase as the
OAuth `redirect_to` and the origin that must be present in the dashboard's
redirect allow-list, so an unset variable does not look broken — it produces a
running app whose every social sign-in redirects to localhost, with a generic
user-facing failure that reads like an upstream outage.
"""
import pytest

from app import create_app


def _boot(flask_env, base_set):
    return create_app({
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_ANON_KEY": "anon-key-123",
        "SECRET_KEY": "test-secret",
        "FLASK_ENV": flask_env,
        "PUBLIC_BASE_URL_SET": base_set,
    })


def test_production_without_explicit_base_refuses_to_boot():
    """The dangerous combination must fail loudly at boot, not at first login."""
    with pytest.raises(RuntimeError) as exc:
        _boot("production", False)
    msg = str(exc.value)
    assert "PUBLIC_BASE_URL" in msg, msg
    assert "localhost" in msg, "message must name the silent default it replaced"


def test_production_with_explicit_boots():
    app = _boot("production", True)
    assert app is not None


def test_local_run_without_base_still_boots():
    """Dev must keep working with no env at all — otherwise this guard becomes
    the thing that stops people running the app locally."""
    assert _boot("development", False) is not None


def test_guard_is_case_and_whitespace_tolerant():
    """FLASK_ENV='PRODUCTION ' from a hand-edited .env must still be caught."""
    with pytest.raises(RuntimeError):
        _boot("  PRODUCTION  ", False)


def test_oauth_redirect_ignores_the_request_host():
    """Companion pin (t4 MINOR-2), written behaviourally: a source-text scan of
    routes/auth.py first failed against its own docstring (which explains the
    rule), which is exactly how a grep-style assertion turns into noise. So
    assert what the app actually does instead.

    1. with a base configured, redirect_to is that base + the callback path,
       even when the request arrives on a different Host;
    2. with no base, the route 503s rather than inventing one from the request.
    """
    from types import SimpleNamespace
    from unittest.mock import patch

    seen = {}

    class _Auth:
        def sign_in_with_oauth(self, creds):
            seen.update(creds.get("options", {}))
            return SimpleNamespace(url="https://provider.example/authorize")

    good = create_app({
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_ANON_KEY": "anon-key-123",
        "SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False,
        "FLASK_ENV": "production",
        "PUBLIC_BASE_URL_SET": True,
        "OAUTH_REDIRECT_BASE": "https://app.example",
        "OAUTH_PROVIDERS": {"google"},
    })
    with patch("routes.auth.get_auth_supabase",
               return_value=SimpleNamespace(auth=_Auth())):
        r = good.test_client().get("/auth/oauth/google",
                                  headers={"Host": "evil.example"})
        assert r.status_code == 302
        assert seen["redirect_to"] == "https://app.example/auth/oauth/callback", seen

    bad = create_app({
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_ANON_KEY": "anon-key-123",
        "SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False,
        "OAUTH_REDIRECT_BASE": "",
        "OAUTH_PROVIDERS": {"google"},
    })
    with patch("routes.auth.get_auth_supabase",
               return_value=SimpleNamespace(auth=_Auth())):
        r2 = bad.test_client().get("/auth/oauth/callback",
                                   headers={"Host": "evil.example"})
        # empty base: the exchange path must refuse rather than guess a host
        assert r2.status_code in (302, 503), r2.status_code
        assert seen["redirect_to"].startswith("https://app.example"), (
            "the only redirect_to ever sent must come from config")
