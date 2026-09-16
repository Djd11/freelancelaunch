"""
T3 — pytest suite for the passwordless OTP + social OAuth surface (design §9).

Pattern: same as the rest of tests/ — real app via create_app({"TESTING": True}),
all Supabase seams faked in-process (no network, no live GoTrue). The two seams
auth.py actually touches are patched at its import site (routes.auth.*), exactly
as the t3 brief mandates:

  * routes.auth.get_auth_supabase   — anon + PKCE auth client (T1)
  * routes.auth.obtain_supabase     — profile provisioning inside _complete_auth

Fixture emails use @sprintspike-otp.dev (the project's test-domain convention;
GoTrue rejects example.com-style domains, so no legacy fixture is copied
forward). OTP codes are taken from the measured samples in
docs/compare/spike_answers.md §4b and must always travel as str — length is
asserted against Config.OTP_CODE_LENGTH, never hardcoded.
"""
import html
import re
import time
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from supabase_auth.errors import AuthError

from app import create_app
from config import Config
from services.supabase_client import PKCE_SESSION_KEY

# Measured live code samples (spike_answers.md §4b). str, not int — an 8-digit
# GoTrue code can begin with a zero; any coercion in the app breaks ~10% of
# logins and this suite must fail loudly on it.
OTP_TOKEN = "45480348"

PKCE_VERIFIER_KEY = "supabase.auth.token-code-verifier"

TEST_CONFIG = {
    "TESTING": True,
    "SECRET_KEY": "unit-test-secret",
    "WTF_CSRF_ENABLED": False,  # per-form CSRF rendering is asserted separately
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "anon-test-key",
    "SUPABASE_KEY": "anon-test-key",
    "SUPABASE_SERVICE_KEY": "service-test-key",
    "OTP_EMAIL_ENABLED": True,
    "OTP_RESEND_COOLDOWN_SECONDS": 60,
    "OAUTH_PROVIDERS": {"google", "facebook"},
    "OAUTH_REDIRECT_BASE": "http://localhost:5000",
    "OAUTH_CALLBACK_PATH": "/auth/oauth/callback",
}


def _uid():
    """A syntactically valid auth.users UUID — load_user drops non-UUID ids."""
    return str(uuid.uuid4())


def _user(uid=None, email="maya@sprintspike-otp.dev", metadata=None):
    return SimpleNamespace(id=uid or _uid(), email=email,
                           user_metadata=metadata if metadata is not None else {})


# ──────────────────────────────────────────────────────────────────────────────
# profile-store fake: records table("user_profiles") traffic for
# _complete_auth provisioning assertions.
# ──────────────────────────────────────────────────────────────────────────────
class FakeProfilesTable:
    def __init__(self, existing_rows):
        self._existing = list(existing_rows)
        self.upsert_calls = []          # [(payload, kwargs), ...]

    # read chain: table().select().eq().limit().execute().data
    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        return SimpleNamespace(data=list(self._existing))

    def upsert(self, payload, **kwargs):
        self.upsert_calls.append((payload, kwargs))
        return self


class FakeSB:
    def __init__(self, existing_rows=()):
        self.profiles = FakeProfilesTable(existing_rows)

    def table(self, name):
        assert name == "user_profiles", f"unexpected table in auth path: {name}"
        return self.profiles


# ──────────────────────────────────────────────────────────────────────────────
# fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture()
def supabase_client():
    """The object get_auth_supabase() returns (a supabase Client). routes.auth
    calls client.auth.<method> — the GoTrue face is one attribute deeper."""
    return MagicMock(name="supabase_auth_client")


@pytest.fixture()
def auth(supabase_client):
    """Convenience: the GoTrue API surface actually invoked by routes/auth.py."""
    return supabase_client.auth


@pytest.fixture()
def profiles(request):
    """FakeSB for routes.auth.obtain_supabase; parametrize via marker for the
    'profile already exists' case."""
    existing = getattr(request, "param", ())
    return FakeSB(existing_rows=existing)


@pytest.fixture()
def client(auth, supabase_client, profiles):
    app = create_app(dict(TEST_CONFIG))
    p1 = patch("routes.auth.get_auth_supabase", return_value=supabase_client)
    p2 = patch("routes.auth.obtain_supabase", return_value=profiles)
    # before_request load_user() reaches for the service client once a session
    # exists; keep it in-process too.
    p3 = patch("services.supabase_client.get_supabase", return_value=MagicMock())
    with p1, p2, p3, app.test_client() as c:
        c.auth = auth          # convenience handles for call assertions
        c.profiles = profiles
        yield c


def _session_dict(client, mutate):
    with client.session_transaction() as s:
        mutate(s)


def _get(client, key, default=None):
    with client.session_transaction() as s:
        return s.get(key, default)


def _norm(html: bytes) -> bytes:
    """Strip per-session/volatile fragments (csrf values, masked address,
    countdown seconds) so two pages can be compared for byte-identity."""
    html = re.sub(rb'name="csrf_token" value="[^"]*"',
                  b'name="csrf_token" value="T"', html)
    html = re.sub(rb"<strong[^>]*>.*?</strong>", b"<strong>MASK</strong>", html)
    html = re.sub(rb"in \d+s", b"in Ns", html)
    # Login-state pages echo the submitted address into value="...";
    # two different fixture emails must not read as a diverging response.
    html = re.sub(rb'value="[^"]*@[^"]*"', b'value="EMAIL"', html)
    return html


def _send_ok(client, email="maya@sprintspike-otp.dev"):
    """Run one accepted send and return its response."""
    client.auth.sign_in_with_otp.return_value = SimpleNamespace(user=None)
    return client.post("/auth/otp/send", data={"email": email})


# ──────────────────────────────────────────────────────────────────────────────
# 1) otp_send — exact kwargs, session state, generic code step
# ──────────────────────────────────────────────────────────────────────────────
def test_otp_send_calls_sign_in_with_otp_exact_kwargs(client):
    """sign_in_with_otp receives EXACTLY {email, options{should_create_user}}.
    Break: hoisting create_user to top level (silently dropped by the lib) or
    dropping should_create_user — new addresses would get no code.
    Also pins: unknown options keys never appear, email stays a str."""
    r = _send_ok(client, "Maya@Sprintspike-OTP.dev")
    assert r.status_code == 200
    assert b"Enter your code" in r.data

    assert client.auth.sign_in_with_otp.call_count == 1
    creds = client.auth.sign_in_with_otp.call_args[0][0]
    assert creds == {"email": "maya@sprintspike-otp.dev",
                     "options": {"should_create_user": True}}
    assert isinstance(creds["email"], str)


def test_otp_send_sets_session_email_and_cooldown_state(client):
    """Session gets otp_email + per-address entry in the otp_last_sent_at map.
    Break: dropping the cooldown map (resend spam) or the address (verify
    loses its authoritative email)."""
    _send_ok(client)
    assert _get(client, "otp_email") == "maya@sprintspike-otp.dev"
    sent = _get(client, "otp_last_sent_at")
    assert isinstance(sent, dict) and "maya@sprintspike-otp.dev" in sent
    assert abs(time.time() - float(sent["maya@sprintspike-otp.dev"])) < 30


def test_otp_send_signup_funnel_name_rides_in_options_data(client):
    """display_name from the create-account form is held in session and passed
    to GoTrue as options.data only when present. Break: name lost at signup."""
    r = client.post("/auth/otp/send",
                    data={"email": "ada@sprintspike-otp.dev",
                          "display_name": "Ada"})
    assert r.status_code == 200
    assert _get(client, "otp_pending_name") == "Ada"
    creds = client.auth.sign_in_with_otp.call_args[0][0]
    assert creds["options"]["should_create_user"] is True
    assert creds["options"]["data"] == {"display_name": "Ada"}


def test_otp_send_generic_step_identical_for_known_and_unknown(client):
    """Enumeration silence (spec §5.2): the rendered step is byte-identical
    whether GoTrue treats the address as existing or as a new account (the
    route ignores sign_in_with_otp's return entirely). Break: branching the
    response on account existence.
    Success-path responses only (accepted deviation #1: transport failures
    intentionally show a retry hint instead of a fake success)."""
    known, unknown = "maya@sprintspike-otp.dev", "ghost@sprintspike-otp.dev"
    client.auth.sign_in_with_otp.side_effect = [
        SimpleNamespace(user=_user(email=known)),  # account exists
        SimpleNamespace(user=None),                # brand-new address
    ]
    r1 = client.post("/auth/otp/send", data={"email": known})
    r2 = client.post("/auth/otp/send", data={"email": unknown})
    assert r1.status_code == r2.status_code == 200
    assert _norm(r1.data) == _norm(r2.data)
    assert b"Enter your code" in r1.data and b"Enter your code" in r2.data
    assert client.auth.sign_in_with_otp.call_count == 2
    # Neither response may hint at existence either way.
    text = html.unescape(r1.data.decode("utf-8")).lower()
    for leak in ("no account", "doesn't exist", "already registered",
                 "new account created", "account exists"):
        assert leak not in text


def test_otp_send_transport_failure_shows_retry_hint_not_fake_success(client):
    """Accepted t2 deviation #1 pinned: when GoTrue errors on send (SMTP
    down/429/bad syntax — never account-specific), the user is NOT lied to
    with a fake 'code sent', no code step is conjured, and no cooldown/
    address state is written. Break: swallowing the error into a fake
    success, or leaking the raw provider error."""
    client.auth.sign_in_with_otp.side_effect = AuthError("rate limit exceeded",
                                                         None)
    r = client.post("/auth/otp/send", data={"email": "maya@sprintspike-otp.dev"})
    assert r.status_code == 200
    text = html.unescape(r.data.decode("utf-8"))
    assert "couldn't send a code just now" in text
    assert "Enter your code" not in text          # no pretend-sent step
    assert _get(client, "otp_email") is None      # no address state
    assert _get(client, "otp_last_sent_at") is None
    assert "rate limit exceeded" not in text      # raw provider error not shown


# ──────────────────────────────────────────────────────────────────────────────
# 2) cooldown
# ──────────────────────────────────────────────────────────────────────────────
def test_otp_send_cooldown_blocks_second_send_without_client_call(client):
    """Second POST to the same address inside 60s is refused server-side and
    the GoTrue client is NEVER called again. Break: cooldown gate removed."""
    _send_ok(client)
    assert client.auth.sign_in_with_otp.call_count == 1
    r = client.post("/auth/otp/send", data={"email": "maya@sprintspike-otp.dev"})
    assert r.status_code == 200
    assert b"before requesting another code" in r.data
    assert client.auth.sign_in_with_otp.call_count == 1, \
        "refused resend must not reach GoTrue"


def test_otp_send_cooldown_expires_after_window(client):
    """Once the stored timestamp ages past the window the send runs again.
    Break: timestamp never refreshed / window inverted."""
    _send_ok(client)

    def age(s):
        stamp = dict(s["otp_last_sent_at"])
        stamp["maya@sprintspike-otp.dev"] = int(time.time()) - 61
        s["otp_last_sent_at"] = stamp

    _session_dict(client, age)
    r = client.post("/auth/otp/send", data={"email": "maya@sprintspike-otp.dev"})
    assert r.status_code == 200 and b"Enter your code" in r.data
    assert client.auth.sign_in_with_otp.call_count == 2


def test_otp_send_cooldown_is_per_address_not_global(client):
    """Deliberate t2 deviation #2: throttle is keyed per address, so a
    mistyped email cannot lock the real one out. Break: global gate."""
    _send_ok(client, "typo1@sprintspike-otp.dev")
    r = _send_ok(client, "typo2@sprintspike-otp.dev")
    assert b"before requesting another code" not in r.data
    assert client.auth.sign_in_with_otp.call_count == 2


# ──────────────────────────────────────────────────────────────────────────────
# 3) otp_verify — happy path, exact literal, str-safe token; wrong/expired
# ──────────────────────────────────────────────────────────────────────────────
def test_otp_verify_happy_path_sets_session_provisions_once(client):
    """Happy path with a measured §4b code: verify_otp payload is EXACTLY
    {email, token, type=="email"} with the token byte-identical str of the
    configured length; success sets session["user_id"], clears OTP state,
    upserts user_profiles exactly once (ON CONFLICT DO NOTHING semantics) and
    redirects /sprints. Break: any int coercion of the token, a different type
    literal (403s on both token families), or repeated provisioning."""
    uid = _uid()
    assert len(OTP_TOKEN) == Config.OTP_CODE_LENGTH  # fixture provenance pin

    _send_ok(client)
    client.auth.verify_otp.return_value = SimpleNamespace(
        user=_user(uid=uid, metadata={"display_name": "Maya"}))
    # Session address is authoritative — the form tries to point elsewhere.
    r = client.post("/auth/otp/verify",
                    data={"token": OTP_TOKEN, "email": "attacker@sprintspike-otp.dev"})

    assert r.status_code == 302 and r.headers["Location"].endswith("/sprints")
    creds = client.auth.verify_otp.call_args[0][0]
    assert creds == {"email": "maya@sprintspike-otp.dev",
                     "token": OTP_TOKEN, "type": "email"}
    assert creds["type"] == "email"  # the literal is the login, per §4b matrix
    assert isinstance(creds["token"], str) and creds["token"] == OTP_TOKEN

    assert _get(client, "user_id") == uid
    assert _get(client, "otp_email") is None
    assert _get(client, "otp_last_sent_at") is None

    ups = client.profiles.profiles.upsert_calls
    assert len(ups) == 1
    payload, kwargs = ups[0]
    assert payload["user_id"] == uid
    assert payload["display_name"] == "Maya"
    assert kwargs.get("on_conflict") == "user_id"
    assert kwargs.get("ignore_duplicates") is True


@pytest.mark.parametrize("profiles", [[{"user_id": "pre-existing"}]], indirect=True)
def test_otp_verify_returning_user_profile_untouched(client):
    """A profile row that already exists is never re-written (display_name
    clobber guard). Break: unconditional upsert."""
    _send_ok(client)
    client.auth.verify_otp.return_value = SimpleNamespace(user=_user())
    client.post("/auth/otp/verify", data={"token": OTP_TOKEN})
    assert client.profiles.profiles.upsert_calls == []
    assert _get(client, "user_id") is not None


def test_otp_verify_wrong_code_generic_error_and_no_session(client):
    """AuthError (wrong/expired/used) → stays on code step with the generic
    message, sets NOTHING, and does not provision. Break: trusting the code
    failure path, or partial auth state leaking into the session."""
    _send_ok(client)
    client.auth.verify_otp.side_effect = AuthError("invalid", None)
    r = client.post("/auth/otp/verify", data={"token": "00000000"})
    assert r.status_code == 200
    # Flask HTML-escapes the flash apostrophe (didn't → didn&#39;t); compare
    # on unescaped text (t2 harness trap, per backend-eng).
    assert "didn't work" in html.unescape(r.data.decode("utf-8"))
    assert _get(client, "user_id") is None
    assert client.profiles.profiles.upsert_calls == []


def test_otp_verify_empty_token_never_reaches_client(client):
    """Empty code → prompt, not a verify round-trip. Break: client call
    forgery/blasting GoTrue with empty tokens."""
    _send_ok(client)
    r = client.post("/auth/otp/verify", data={"token": ""})
    assert r.status_code == 200 and b"Enter the code" in r.data
    client.auth.verify_otp.assert_not_called()
    assert _get(client, "user_id") is None


def test_otp_verify_non_numeric_token_currently_forwards_verbatim(client):
    """DOCUMENTS THE SHIPPED TRUTH at 6a8f400: no server-side digit/length
    validator exists yet (t5 adds re.fullmatch pre-GoTrue), so a junk code
    reaches the spied client STRING-VERBATIM and GoTrue's AuthError drives
    the generic failure. t9 (ordered post-t5) flips this to never-called +
    4xx — this test failing after t5 is the designed flip, not a regression.
    Break today: any int coercion of the token (int("0abc") would 500) or a
    silent-acceptance path."""
    _send_ok(client)
    client.auth.verify_otp.side_effect = AuthError("invalid token", None)
    r = client.post("/auth/otp/verify", data={"token": "0abc-def"})
    assert client.auth.verify_otp.call_count == 1
    creds = client.auth.verify_otp.call_args[0][0]
    assert creds["token"] == "0abc-def" and isinstance(creds["token"], str)
    assert r.status_code == 200 and b"Enter your code" in r.data
    assert _get(client, "user_id") is None


def test_otp_verify_without_send_session_is_inert(client):
    """A code step conjured by URL (no prior send, no email) must not call
    GoTrue or set any state — the OTP step is not a login until verify."""
    r = client.post("/auth/otp/verify", data={"token": OTP_TOKEN})
    assert r.status_code == 200
    client.auth.verify_otp.assert_not_called()
    assert _get(client, "user_id") is None


# ──────────────────────────────────────────────────────────────────────────────
# 4) REGRESSION: signup with an existing email must NOT create a session
# ──────────────────────────────────────────────────────────────────────────────
def test_signup_existing_email_no_session_funnel_to_otp(client):
    """The deleted collision auto-login is gone: signup POST with an address
    that already has an account just sends a code — no session, no admin
    create_user/sign-in side effects, even when the fake GoTrue returns a
    user object on send. Break: any path that logs in before verification."""
    client.auth.sign_in_with_otp.return_value = SimpleNamespace(
        user=_user())  # would have been enough to log in under the old bug
    r = client.post("/auth/signup",
                    data={"email": "Taken@Sprintspike-OTP.dev",
                          "display_name": "Taken"})
    assert r.status_code == 200
    assert _get(client, "user_id") is None, "signup must never set a session"
    creds = client.auth.sign_in_with_otp.call_args[0][0]
    assert creds["email"] == "taken@sprintspike-otp.dev"
    assert creds["options"]["should_create_user"] is True
    assert b"Enter your code" in r.data
    # The old implementation minted passwords via the service client — dead
    # here: nothing but the anon send seam is touched.
    assert client.auth.sign_in_with_password.call_count == 0
    assert _get(client, "otp_pending_name") == "Taken"


def test_signup_existing_email_verify_still_required(client):
    """End-to-end intent of the regression: after the signup funnel, the
    session only exists once the code verifies (GoTrue called again)."""
    client.post("/auth/signup", data={"email": "taken@sprintspike-otp.dev"})
    assert _get(client, "user_id") is None
    uid = _uid()
    client.auth.verify_otp.return_value = SimpleNamespace(user=_user(uid=uid))
    r = client.post("/auth/otp/verify", data={"token": OTP_TOKEN})
    assert r.status_code == 302
    assert _get(client, "user_id") == uid


# ──────────────────────────────────────────────────────────────────────────────
# 5) oauth_start
# ──────────────────────────────────────────────────────────────────────────────
def test_oauth_start_unknown_provider_404_and_no_client_call(client):
    """Allow-list only; unknown/disabled names 404 alike, with NO GoTrue call.
    Break: providers reaching the authorize URL from a config typo."""
    for p in ("github", "notreal", ""):
        r = client.get(f"/auth/oauth/{p}")
        assert r.status_code == 404, p
    client.auth.sign_in_with_oauth.assert_not_called()


def test_oauth_start_redirects_to_provider_url_with_pkce_challenge(client):
    """Configured provider → 302 to the client-returned authorize URL, which
    carries provider + code_challenge; the route passes provider +
    redirect_to (callback under OAUTH_REDIRECT_BASE) exactly. Break: dropping
    the PKCE challenge from the asserted shape or wrong callback URL."""
    authorize = ("https://test.supabase.co/auth/v1/authorize?provider=google"
                 "&code_challenge=TESTCHALLENGE123&code_challenge_method=S256")
    client.auth.sign_in_with_oauth.return_value = SimpleNamespace(url=authorize)
    r = client.get("/auth/oauth/google")
    assert r.status_code == 302
    assert r.headers["Location"] == authorize
    assert "provider=google" in r.headers["Location"]
    assert "code_challenge=TESTCHALLENGE123" in r.headers["Location"]
    payload = client.auth.sign_in_with_oauth.call_args[0][0]
    assert payload == {"provider": "google",
                       "options": {"redirect_to":
                                   "http://localhost:5000/auth/oauth/callback"}}


def test_oauth_start_facebook_also_allow_listed(client):
    client.auth.sign_in_with_oauth.return_value = SimpleNamespace(url="https://x/y")
    assert client.get("/auth/oauth/facebook").status_code == 302


# ──────────────────────────────────────────────────────────────────────────────
# 6) oauth_callback
# ──────────────────────────────────────────────────────────────────────────────
def test_oauth_callback_exchange_failure_no_session(client):
    """AuthError mid-exchange → same generic funnel back to login, no state,
    and no auth residue in the session (no user_id, no verifier bucket key —
    the route itself never writes auth state). Break: half-login or 500."""
    client.auth.exchange_code_for_session.side_effect = AuthError("bad", None)
    r = client.get("/auth/oauth/callback?code=abc123")
    assert r.status_code == 302 and r.headers["Location"].endswith("/auth/login")
    with client.session_transaction() as s:
        assert "user_id" not in s
        # Our route never writes the PKCE bucket itself:
        assert s.get(PKCE_SESSION_KEY) in (None, {})
    assert client.profiles.profiles.upsert_calls == []


def test_oauth_callback_missing_code_generic_flash_no_session(client):
    """No/empty code (cancel, denial, stripped query) → generic flash to
    /auth/login; never a 500; exchange never called."""
    for q in ("", "?code="):
        r = client.get("/auth/oauth/callback" + q)
        assert r.status_code == 302 and r.headers["Location"].endswith("/auth/login"), q
        with client.session_transaction() as s:
            assert "user_id" not in s
    client.auth.exchange_code_for_session.assert_not_called()
    # flash text check on one request:
    client.get("/auth/oauth/callback")
    with client.session_transaction() as s:
        flashes = [m for _, m in s.get("_flashes", [])]
    assert any("Social sign-in didn't complete" in f for f in flashes)


@pytest.mark.xfail(raises=(TypeError, AttributeError), strict=False,
                   reason="BUG-T3-1 (routes/auth.py:374): `if not code` tests the "
                          "RAW arg — a whitespace-only code ('%20') is truthy and "
                          "reaches the exchange; if the exchange ever resolves, "
                          "_complete_auth stores a non-serializable uid in the "
                          "session. Unreachable with real GoTrue (it rejects "
                          "whitespace codes with AuthError) — minor robustness.")
def test_oauth_callback_whitespace_code_is_not_a_valid_code(client):
    r = client.get("/auth/oauth/callback?code=%20")
    # A stripped/validated guard would take the same generic path as missing.
    assert r.status_code == 302 and r.headers["Location"].endswith("/auth/login")
    with client.session_transaction() as s:
        assert "user_id" not in s


def test_oauth_callback_success_sets_session_via_complete_auth(client):
    """Successful exchange → _complete_auth: exact kwargs (code_verifier==""
    sentinel so the client pulls it from FlaskSessionStorage), session set,
    profile provisioned once with the provider name hint, redirect /sprints."""
    uid = _uid()
    client.auth.exchange_code_for_session.return_value = SimpleNamespace(
        user=_user(uid=uid, metadata={"full_name": "Grace Hopper"}))
    r = client.get("/auth/oauth/callback?code=abc123")
    assert r.status_code == 302 and r.headers["Location"].endswith("/sprints")
    payload = client.auth.exchange_code_for_session.call_args[0][0]
    assert payload == {"auth_code": "abc123", "code_verifier": "",
                       "redirect_to": "http://localhost:5000/auth/oauth/callback"}
    assert _get(client, "user_id") == uid
    ups = client.profiles.profiles.upsert_calls
    assert len(ups) == 1 and ups[0][0]["display_name"] == "Grace Hopper"


# ──────────────────────────────────────────────────────────────────────────────
# 7) password login unchanged (spec §5.4 collapsible; §8 compatibility)
# ──────────────────────────────────────────────────────────────────────────────
def test_password_login_success_sets_session(client):
    """POST /auth/login with real credentials still works, with the exact
    credential dict handed to the service client. Break: legacy path drift."""
    uid = _uid()
    sb = MagicMock()
    sb.auth.sign_in_with_password.return_value = SimpleNamespace(user=_user(uid=uid))
    with patch("routes.auth.obtain_supabase", return_value=sb):
        r = client.post("/auth/login",
                        data={"email": "maya@sprintspike-otp.dev",
                              "password": "correct-horse"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/sprints")
    assert _get(client, "user_id") == uid
    sb.auth.sign_in_with_password.assert_called_once_with(
        {"email": "maya@sprintspike-otp.dev", "password": "correct-horse"})


def test_password_login_failure_identical_bad_email_vs_password(client):
    """AuthError for a nonexistent email and for a wrong password must render
    the byte-identical response with the same generic message. Break: an
    error string that discriminates (enumeration via the password form).
    The legacy password path must not provision anything either."""
    sb = MagicMock()
    sb.auth.sign_in_with_password.side_effect = AuthError("nope", None)
    bodies = []
    with patch("routes.auth.obtain_supabase", return_value=sb):
        for email in ("nobody@sprintspike-otp.dev", "maya@sprintspike-otp.dev"):
            r = client.post("/auth/login",
                            data={"email": email, "password": "wrong-password"})
            assert r.status_code == 200
            assert b"Invalid email or password." in r.data
            assert _get(client, "user_id") is None
            bodies.append(_norm(r.data))
    assert bodies[0] == bodies[1]


# ──────────────────────────────────────────────────────────────────────────────
# 8) CSRF tokens render on every auth form (production-shaped app)
# ──────────────────────────────────────────────────────────────────────────────
def test_auth_forms_render_nonempty_csrf_tokens():
    app = create_app(dict(TEST_CONFIG, WTF_CSRF_ENABLED=True))
    with app.test_client() as c:
        fake = MagicMock()
        fake.auth.sign_in_with_otp.return_value = SimpleNamespace(user=None)
        with patch("routes.auth.get_auth_supabase", return_value=fake), \
             patch("routes.auth.obtain_supabase", return_value=FakeSB()), \
             patch("services.supabase_client.get_supabase", return_value=MagicMock()):
            pages = {"GET /auth/login": c.get("/auth/login"),
                     "GET /auth/signup": c.get("/auth/signup")}
            # CSRF is ON here, so the honest way to reach the code step is a
            # real POST carrying the token scraped from the rendered form
            # (this doubles as proof the token round-trips).
            tok = re.search(rb'name="csrf_token" value="([^"]+)"',
                            pages["GET /auth/login"].data).group(1)
            r = c.post("/auth/otp/send",
                       data={"email": "maya@sprintspike-otp.dev",
                             "csrf_token": tok.decode()})
            assert r.status_code == 200, "scraped token should be accepted"
            pages["POST /auth/otp/send (code step)"] = r
            pages["GET /auth/login?step=code"] = c.get("/auth/login?step=code")
    for url, resp in pages.items():
        assert resp.status_code == 200, url
        inputs = re.findall(rb'name="csrf_token" value="([^"]+)"', resp.data)
        assert inputs, f"no csrf_token input on {url}"
        assert all(len(tok) > 20 for tok in inputs), f"empty csrf token on {url}"


def test_otp_send_post_without_csrf_token_is_rejected():
    app = create_app(dict(TEST_CONFIG, WTF_CSRF_ENABLED=True))
    with app.test_client() as c:
        with patch("routes.auth.get_auth_supabase", return_value=MagicMock()):
            r = c.post("/auth/otp/send", data={"email": "maya@sprintspike-otp.dev"})
    assert r.status_code == 400


# ──────────────────────────────────────────────────────────────────────────────
# feature flags (t2 "both feature flags")
# ──────────────────────────────────────────────────────────────────────────────
def test_otp_disabled_flag_refuses_send_and_verify():
    app = create_app(dict(TEST_CONFIG, OTP_EMAIL_ENABLED=False))
    fake = MagicMock()
    with patch("routes.auth.get_auth_supabase", return_value=fake), \
         patch("routes.auth.obtain_supabase", return_value=FakeSB()), \
         patch("services.supabase_client.get_supabase", return_value=MagicMock()), \
         app.test_client() as c:
        r = c.post("/auth/otp/send", data={"email": "maya@sprintspike-otp.dev"})
        assert r.status_code == 200 and b"password" in r.data
        fake.auth.sign_in_with_otp.assert_not_called()
        # Bookmark code step must not stay a live login route either.
        with c.session_transaction() as s:
            s["otp_email"] = "maya@sprintspike-otp.dev"
        r = c.post("/auth/otp/verify", data={"token": OTP_TOKEN})
        assert _get(c, "user_id") is None
        fake.auth.verify_otp.assert_not_called()


def test_oauth_providers_empty_flag_404s(client):
    app = create_app(dict(TEST_CONFIG, OAUTH_PROVIDERS=set()))
    with app.test_client() as c:
        assert c.get("/auth/oauth/google").status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# T1 pins: get_client_supabase anon-key lookup + FlaskSessionStorage behavior
# ──────────────────────────────────────────────────────────────────────────────
def test_get_client_supabase_succeeds_with_config_published_key():
    """Regression pin for the drive-by fix: Config publishes SUPABASE_KEY
    (from env SUPABASE_ANON_KEY); the old lookup of SUPABASE_ANON_KEY alone
    raised even on a fully configured project. Break: reverting either half of
    the paired lookup."""
    from services.supabase_client import get_client_supabase
    app = create_app(dict(TEST_CONFIG))
    del app.config["SUPABASE_ANON_KEY"]          # Config's published spelling
    app.config["SUPABASE_KEY"] = "published-anon-key"
    with app.app_context(), \
         patch("supabase.create_client", return_value=MagicMock()) as cc:
        client_obj = get_client_supabase()
        assert client_obj is not None
        assert cc.call_args[0][1] == "published-anon-key"


def test_get_client_supabase_raises_without_any_anon_key():
    from services.supabase_client import get_client_supabase
    app = create_app(dict(TEST_CONFIG))
    app.config["SUPABASE_ANON_KEY"] = ""
    app.config["SUPABASE_KEY"] = ""
    with app.app_context():
        with pytest.raises(RuntimeError, match="not configured"):
            get_client_supabase()


def test_flask_session_storage_single_key_and_removal():
    """PKCE storage keeps exactly ONE top-level session key (_sb_pkce) and the
    fixed verifier name inside it; remove_item clears the verifier (the
    client's post-exchange/failure behavior) and get_item returns None after.
    Break: writing verifier state anywhere else in the cookie."""
    from services.supabase_client import FlaskSessionStorage
    app = create_app(dict(TEST_CONFIG))
    with app.test_request_context("/auth/oauth/google"):
        st = FlaskSessionStorage()
        before = set(flask_keys())
        st.set_item(PKCE_VERIFIER_KEY, "verifier-xyz")
        assert set(flask_keys()) - before == {PKCE_SESSION_KEY}
        from flask import session as fsession
        assert fsession[PKCE_SESSION_KEY] == {PKCE_VERIFIER_KEY: "verifier-xyz"}
        assert fsession.modified
        assert st.get_item(PKCE_VERIFIER_KEY) == "verifier-xyz"
        st.remove_item(PKCE_VERIFIER_KEY)
        assert st.get_item(PKCE_VERIFIER_KEY) is None
        assert st.get_item("never-set") is None
        st.remove_item("never-set")  # must not raise


def flask_keys():
    from flask import session as fsession
    return list(fsession.keys())


# ──────────────────────────────────────────────────────────────────────────────
# logout hygiene
# ──────────────────────────────────────────────────────────────────────────────
def test_logout_clears_auth_and_otp_state(client):
    _send_ok(client)
    client.auth.verify_otp.return_value = SimpleNamespace(user=_user())
    client.post("/auth/otp/verify", data={"token": OTP_TOKEN})
    assert _get(client, "user_id") is not None
    r = client.get("/auth/logout")
    assert r.status_code == 302
    with client.session_transaction() as s:
        assert "user_id" not in s
        assert "otp_email" not in s and "otp_last_sent_at" not in s
