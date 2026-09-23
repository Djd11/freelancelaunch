"""OTP / social-login UAT harness (uat-validator).

Two jobs, deliberately separated:

  1. LIVE helpers (talk to the real Supabase project) — *rate-limited and capped by
     a ledger*, because the dev project's built-in SMTP is ~2 emails/hour and the
     captain capped test-auth-user creation at 8 for the whole run:
        mint_user(email)   -> admin signup link  (NO email sent, creates auth user)
        otp_for(email)     -> admin magiclink    (NO email sent, returns email_otp + hashed_token)
        live_otp_send(...) -> POST /auth/otp/send for real (BURNS 1 SMTP email; budget-gated)

  2. FAKES (in-process, zero email, zero GoTrue) — everything that is not the single
     live end-to-end proof runs against a recorded fake auth client so the window's
     SMTP budget survives: A3 cooldown, A4 replay, A5 failures, A6 collision,
     A8/A9 OAuth start + callback (incl. a faked *successful* exchange, which is the
     only way to exercise the OAuth success -> _complete_auth leg without Google creds).

Honesty rule baked into the API: a test that ran under fakes must say so. Use
`FakeAuth.calls` as the evidence that the app really invoked sign_in_with_otp /
verify_otp with the arguments the spec requires (type literal, should_create_user,
flow_type/PKCE), and mark such evidence `FAKE-TRANSPORT` in the report.

Seam discovery is lazy on purpose: routes/auth.py and supabase_client.py churn
through the review tasks, so the harness resolves the auth-client factory at run
time and refuses to guess if it cannot find it.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

LEDGER = Path(__file__).resolve().parents[1] / "reports" / "otp_live_budget.json"
MAX_TEST_USERS = 8          # captain's hard cap for the whole run
MAX_LIVE_SENDS_PER_HOUR = 2  # built-in SMTP ceiling; leave the 3rd slot for a retry

# ADDRESS SPACE — captain's OVERRIDE, binding (message 5, after T1's measurements):
# GoTrue rejects `@example.com` / `@example.org` / `@*.invalid` at signup (`email_address_invalid`),
# so his original `uat-otp-*@example.com` cap was unusable. The sanctioned pattern is now
# `uat-otp-*@sprintspike-otp.dev` — well-formed, unregistered label (undeliverable), measured accepted.
# `example.com` stays in the list ONLY so the ledger can still account for the one identity minted
# before the override landed (`uat-otp-a5@example.com`, uuid 9c2714bf-aa18-4ab6-a2e9-ee2306560cee),
# which is residue, not a fixture: no live send can use it. New writes default to the .dev space.
UAT_ADDRESS_DOMAINS = tuple(
    d.strip() for d in os.environ.get(
        "UAT_DOMAINS", "sprintspike-otp.dev,example.com").split(",") if d.strip()
)   # first entry is the sanctioned default; prefix + cap + ledger do the safety work
UAT_ADDRESS_PREFIX = "uat-otp-"


# --------------------------------------------------------------------------- #
# live-budget ledger (mechanical enforcement of the captain's caps)
# --------------------------------------------------------------------------- #
def _ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"users": [], "sends": [], "notes": []}


def _save_ledger(d: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    d["sends"] = [s for s in d["sends"] if time.time() - s < 3600]
    LEDGER.write_text(json.dumps(d, indent=2, sort_keys=True))


def _spend_send_slot() -> None:
    d = _ledger()
    recent = [s for s in d["sends"] if time.time() - s < 3600]
    if len(recent) >= MAX_LIVE_SENDS_PER_HOUR:
        wait = int(3600 - (time.time() - min(recent))) + 5
        raise RuntimeError(
            f"LIVE OTP send budget exhausted ({len(recent)}/{MAX_LIVE_SENDS_PER_HOUR} "
            f"in the last hour). Next slot in ~{wait}s. Use fakes for everything else."
        )
    recent.append(time.time())
    d["sends"] = recent
    _save_ledger(d)


def _spend_user_slot(email: str) -> None:
    d = _ledger()
    if email in d["users"]:
        return
    if len(d["users"]) >= MAX_TEST_USERS:
        raise RuntimeError(f"test-user cap reached ({MAX_TEST_USERS}): {d['users']}")
    d["users"].append(email)
    _save_ledger(d)


def assert_uat_email(email: str) -> None:
    """Only the sanctioned throwaway space may ever be written to, whatever domain is in force."""
    ok = (email.startswith(UAT_ADDRESS_PREFIX)
          and email.rsplit("@", 1)[-1].lower() in [d.lower() for d in UAT_ADDRESS_DOMAINS])
    if not ok:
        raise RuntimeError(
            f"refusing to write: {email!r} is outside the sanctioned space "
            f"{UAT_ADDRESS_PREFIX}*@" + "/".join(UAT_ADDRESS_DOMAINS)
            + " (override with UAT_DOMAINS only after the captain re-approves)")


# --------------------------------------------------------------------------- #
# LIVE: admin link minting (sends no email)
# --------------------------------------------------------------------------- #
def _service_client():
    os.environ.setdefault("SUPABASE_ENV_QUIET", "1")
    from supabase import create_client  # noqa: WPS433

    sys.path.insert(0, str(REPO))
    envf = REPO / ".env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
    if not (url and key):
        raise RuntimeError("no SUPABASE_URL/SERVICE key in .env")
    return create_client(url, key)


def mint_user(email: str, password: str | None = None) -> dict:
    """Create a live auth user via admin signup link. No email is sent."""
    assert_uat_email(email)
    _spend_user_slot(email)
    sb = _service_client()
    password = password or "uat-" + os.urandom(6).hex() + "-unused"
    res = sb.auth.admin.generate_link({"type": "signup", "email": email, "password": password})
    return {
        "email": email,
        "id": res.user.id,
        "email_confirmed_at": getattr(res.user, "email_confirmed_at", None),
        "email_otp": res.properties.email_otp,
        "hashed_token": _hashed(res.properties.action_link),
        "verification_type": getattr(res.properties, "verification_type", None),
    }


def _admin_link(email: str, link_type: str = "magiclink") -> dict:
    """Mint a code of a chosen family through the admin API. **Sends no mail.**

    Two rulings shape this helper. (1) The captain's: `generate_link` does NOT reproduce what our
    `/otp/send` mints (the type is ours to choose here), so evidence from it is "which codes the
    shipped literal accepts", not end-to-end email-OTP proof — G1 (operator `{{ .Token }}` + custom
    SMTP) stays the named gap. (2) Spike trap #3: an OTP is single-use, so **every** case needs its
    own fresh token or a reused one fabricates a rejection that looks like a type-literal bug.
    A `signup` mint on an unknown address creates that user, so it spends one of the 8 slots;
    a `magiclink` mint on an existing address creates nobody and is not charged.
    """
    assert_uat_email(email)
    exists = user_id(email) is not None
    if not exists and link_type == "signup":
        _spend_user_slot(email)
    sb = _service_client()
    params: dict = {"type": link_type, "email": email}
    if link_type == "signup":
        params["password"] = "uat-" + os.urandom(6).hex() + "-unused"
    res = sb.auth.admin.generate_link(params)
    return {
        "email": email,
        "id": res.user.id,
        "email_otp": res.properties.email_otp,
        "email_confirmed_at": getattr(res.user, "email_confirmed_at", None),
        "created_by_this_call": not exists and link_type == "signup",
        "hashed_token": _hashed(res.properties.action_link),
        "verification_type": getattr(res.properties, "verification_type", None),
    }


def otp_for(email: str) -> dict:
    """Mint the code GoTrue would have emailed, without sending mail."""
    sb = _service_client()
    res = sb.auth.admin.generate_link({"type": "magiclink", "email": email})
    return {
        "email": email,
        "id": res.user.id,
        "email_otp": res.properties.email_otp,
        "hashed_token": _hashed(res.properties.action_link),
        "verification_type": getattr(res.properties, "verification_type", None),
    }


def _hashed(action_link: str) -> str | None:
    import urllib.parse as _up

    if not action_link:
        return None
    q = _up.parse_qs(_up.urlsplit(action_link).query)
    return (q.get("token") or [None])[0]


def live_otp_send(client, email: str, *, path: str = "/auth/otp/send", extra: dict | None = None):
    """A REAL send: burns 1 of the 2/hour SMTP slots, so it is ledger-gated.

    `client` is a Flask test client (or anything with .post()). Returns the response;
    the caller records status/body as evidence.
    """
    assert_uat_email(email)
    _spend_send_slot()
    data = {"email": email}
    data.update(extra or {})
    tok = csrf_token(client)
    if tok:
        data.setdefault("csrf_token", tok)
    return client.post(path, data=data, follow_redirects=False)


def profile_rows(email: str) -> list[dict]:
    """Read-only: `user_profiles` rows for an email (duplicate-provisioning check).

    The table is keyed by the **`user_id`** column (routes/auth.py:_complete_auth queries
    `.eq("user_id", uid)`), NOT by a column named `id` — querying the wrong name returns an
    empty list and would fabricate a "not provisioned" finding, so this is pinned deliberately.
    """
    sb = _service_client()
    uid = user_id(email)
    if not uid:
        return []
    return sb.table("user_profiles").select("*").eq("user_id", uid).execute().data or []


def user_id(email: str) -> str | None:
    sb = _service_client()
    for u in sb.auth.admin.list_users():
        if (u.email or "").lower() == email.lower():
            return u.id
    return None


# --------------------------------------------------------------------------- #
# FAKE auth client (zero SMTP, zero GoTrue)
# --------------------------------------------------------------------------- #
class FakeAuth:
    """Duck-typed stand-in for the PKCE anon client's `.auth`.

    Configure `verify_result` / `exchange_result` per test:
      "ok"      -> returns the scripted user/session
      "error"   -> raises AuthApiError-like failure (failure-path evidence)
      ("none")  -> returns AuthResponse(user=None, session=None)
    Every call is recorded in `self.calls` — that list IS the assertion payload
    for spec claims like "verify_otp called with type='email'".
    """

    def __init__(self, *, uid: str, email: str, name_hint: str | None = None):
        self.uid, self.email, self.name_hint = uid, email, name_hint
        self.calls: list[dict] = []
        self.verify_result = "ok"
        self.exchange_result = "ok"
        self.otp_result = "ok"
        self.expected_token: str | None = None
        # Only used if a test *needs* a faked start; the real client builds this URL locally
        # (no network), so A8 should prefer the REAL client — see run_t7_uat.step7_oauth.
        self.oauth_url = "https://fake-project.supabase.co/auth/v1/authorize"

    # -- helpers ---------------------------------------------------------- #
    def _user(self):
        from supabase_auth.types import User

        return User(
            id=self.uid,
            email=self.email,
            app_metadata={"provider": "email"},
            user_metadata={"display_name": self.name_hint or self.email.split("@")[0],
                           "email": self.email},
            aud="authenticated",
            email_confirmed_at="2026-01-01T00:00:00Z",
            created_at="2026-01-01T00:00:00Z",
            last_sign_in_at="2026-01-01T00:00:00Z",
            phone=None,
            identities=[],
        )

    def _session(self, provider: str = "email"):
        from supabase_auth.types import Session

        user = self._user()
        return Session(
            provider_token=None, provider_refresh_token=None,
            access_token="uat-fake-jwt-access", refresh_token="uat-fake-refresh",
            expires_in=3600, expires_at=int(time.time()) + 3600,
            token_type="bearer", user=user,
        )

    def _fail(self, msg: str, status: int = 400):
        from supabase_auth.errors import AuthApiError

        return AuthApiError(msg, status=status, code="bad_otp")

    # -- client surface used by routes/auth.py ---------------------------- #
    def sign_in_with_otp(self, credentials: dict):
        self.calls.append({"m": "sign_in_with_otp", "args": _plain(credentials)})
        from supabase_auth.types import AuthOtpResponse

        if self.otp_result == "error":
            raise self._fail("Rate limit exceeded")
        return AuthOtpResponse(user=None, session=None, message_id="uat-fake-message-id")

    def verify_otp(self, params: dict):
        self.calls.append({"m": "verify_otp", "args": _plain(params)})
        from supabase_auth.types import AuthResponse

        if self.verify_result == "error":
            raise self._fail("Token has expired or is invalid")
        if self.verify_result == "none":
            return AuthResponse(user=None, session=None)
        if self.expected_token is not None and params.get("token") != self.expected_token:
            return AuthResponse(user=None, session=None)
        return AuthResponse(user=self._user(), session=self._session())

    def resend(self, params: dict):
        self.calls.append({"m": "resend", "args": _plain(params)})
        from supabase_auth.types import AuthOtpResponse

        return AuthOtpResponse(user=None, session=None, message_id="uat-fake-resend")

    def sign_in_with_oauth(self, provider: str, options: dict | None = None):
        self.calls.append({"m": "sign_in_with_oauth", "args": {"provider": provider,
                                                               "options": _plain(options or {})}})
        from supabase_auth.types import OAuthResponse

        # Real client returns OAuthResponse(provider=…, url=…) — a tuple here made the route 500
        # in my own self-test, which would have looked like a product bug.
        return OAuthResponse(provider=provider, url=self.oauth_url)

    def exchange_code_for_session(self, params: dict):
        self.calls.append({"m": "exchange_code_for_session", "args": _plain(params)})
        from supabase_auth.types import AuthResponse

        if self.exchange_result == "error":
            raise self._fail("invalid code")
        if self.exchange_result == "none":
            return AuthResponse(user=None, session=None)
        return AuthResponse(user=self._user(), session=self._session(provider="google"))

    def get_user(self, *_a, **_k):
        from supabase_auth.types import AuthResponse

        return AuthResponse(user=self._user(), session=self._session())

    def sign_out(self, *_a, **_k):
        self.calls.append({"m": "sign_out", "args": {}})
        return None

    @property
    def _http_client(self):
        class _C:
            def close(self_inner):
                pass
        return _C()

    def last(self, method: str) -> dict | None:
        for c in reversed(self.calls):
            if c["m"] == method:
                return c["args"]
        return None


def _plain(v):
    """JSON-safe view of call args (so evidence can be pasted into the report)."""
    try:
        json.dumps(v)
        return v
    except TypeError:
        if isinstance(v, dict):
            return {k: _plain(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [_plain(x) for x in v]
        return repr(v)


# --------------------------------------------------------------------------- #
# app factory with the auth seam swapped for a FakeAuth
# --------------------------------------------------------------------------- #
SEAM_CANDIDATES = ("get_auth_supabase", "get_pkce_supabase", "get_auth_client")


def make_app(fake: FakeAuth, *, oauth_providers: str | None = None,
             otp_email_enabled: str | None = None):
    """create_app() with the request-scoped auth client replaced by `fake`.

    `get_supabase()` / `get_client_supabase()` stay REAL: provisioning,
    user_profiles reads and every other route keep hitting the live project, so
    `_complete_auth` and the session contract are still proven for real.
    """
    from app import create_app

    # Config computes OAUTH_PROVIDERS / OTP_EMAIL_ENABLED at CLASS-BODY evaluation (config.py:39-41,
    # 72-73), i.e. once at first import — so setting os.environ after import changes nothing and my
    # first A11 pass falsely "failed". In production the env is set before the process starts, so
    # that is correct behaviour; in-process I must inject config overrides instead.
    overrides: dict = {}
    if oauth_providers is not None:
        overrides["OAUTH_PROVIDERS"] = {p for p in
                                        (x.strip().lower() for x in oauth_providers.split(",")) if p}
    if otp_email_enabled is not None:
        overrides["OTP_EMAIL_ENABLED"] = str(otp_email_enabled).lower() not in ("0", "false", "no", "")

    app = create_app(overrides) if overrides else create_app()

    import services.supabase_client as sc
    import routes.auth as ra

    fake_client = type("FakeAuthClient", (), {"auth": fake})()
    resolved = None
    for name in SEAM_CANDIDATES:
        if hasattr(sc, name):
            resolved = name
            break
    if resolved is None:
        raise RuntimeError(
            "auth-client factory not found in services/supabase_client.py yet "
            f"(looked for {SEAM_CANDIDATES}). Spec name is 'get_auth_supabase'. "
            "Do NOT fake around a seam you cannot see — this means the build is not ready."
        )
    setattr(sc, resolved, lambda: fake_client)
    # routes may import the factory by name at module load: patch those too
    for name in SEAM_CANDIDATES:
        if hasattr(ra, name):
            setattr(ra, name, lambda: fake_client)
    app.config["TESTING"] = False
    app._uat_fake_seam = resolved
    return app


def client_for(app, *, fresh: bool = True):
    """Flask test client (cookie jar isolated per call-site)."""
    return app.test_client()


def csrf_token(client, page: str = "/auth/login") -> str | None:
    """Scrape the form token the way a browser gets it (same cookie jar, same session).

    The app runs Flask-WTF CSRF, so a POST without `csrf_token` answers 400 — my first self-test
    hit exactly that and every fake step "failed" with 0 transport calls, which looked like a
    product regression and was only my harness. UAT must send what a browser sends.
    """
    import re

    html = client.get(page).get_data(as_text=True)
    m = (re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
         or re.search(r'value="([^"]+)"[^>]*name="csrf_token"', html))
    return m.group(1) if m else None


def post_form(client, path: str, data: dict | None = None, *, token_page: str = "/auth/login",
              **kw):
    """CSRF-correct POST. A 400 from this helper is a genuine finding, not a harness artifact."""
    body = dict(data or {})
    tok = csrf_token(client, token_page)
    if tok:
        body.setdefault("csrf_token", tok)
    return client.post(path, data=body, **kw)


def flash_text(resp_html: str) -> str:
    import re

    hits = re.findall(r'(?s)<(?:p|div|li|span)[^>]*(?:flash|alert|message|error)[^>]*>(.*?)<',
                      resp_html or "")
    return " | ".join(h.strip() for h in hits if h.strip())


def stamp() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    # Self-check only: proves the fake models are constructible with this venv.
    f = FakeAuth(uid="11111111-1111-1111-1111-111111111111", email="uat-otp-selftest@example.com")
    f._user(); f._session()
    print("FakeAuth models OK; ledger:", LEDGER, "seam candidates:", SEAM_CANDIDATES)
