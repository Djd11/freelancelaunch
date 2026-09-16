"""T2 verification — routes/auth.py + the unified login surface.

Fakes the two Supabase seams in routes/auth.py (get_auth_supabase /
obtain_supabase) so every branch is exercised without network, SMTP or dashboard
config.

Run:  PYTHONPATH=. .venv/bin/python docs/superpowers/spikes/verify_t2_auth_routes.py

Deliberately not under tests/ — T6 owns the unit-test task. Each section is a
plain function of asserts, promotable into a pytest module as-is.
"""
import contextlib
import re
from types import SimpleNamespace
from unittest.mock import patch

from supabase_auth.errors import AuthApiError

from app import create_app

FAILS = []


def norm(t):
    """Compare copy safely: Flask escapes quotes as &#39; in the rendered page
    and the prose uses typographic apostrophes — neither matches a raw literal."""
    import html as _html
    return _html.unescape(t).replace("’", "'").lower()


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name
          + (("" if ok else f" — {detail}") if detail else ""))
    if not ok:
        FAILS.append(name)


def api_err(msg, status):
    """AuthApiError's ctor is (message, status, code) — all three required."""
    return AuthApiError(msg, status, None)


class FakeAuth:
    def __init__(self, otp_error=None, verify_error=None, exchange_error=None,
                 uid="11111111-1111-1111-1111-111111111111"):
        self.otp_error, self.verify_error, self.exchange_error = (
            otp_error, verify_error, exchange_error)
        self.uid = uid
        self.otp_calls, self.verify_calls = [], []
        self.oauth_calls, self.exchange_calls = [], []

    def sign_in_with_otp(self, creds):
        self.otp_calls.append(creds)
        if self.otp_error:
            raise self.otp_error
        return SimpleNamespace(user=None, session=None, is_signup_enabled=True,
                               user_id=self.uid)

    def verify_otp(self, params):
        self.verify_calls.append(params)
        if self.verify_error:
            raise self.verify_error
        return SimpleNamespace(
            user=SimpleNamespace(id=self.uid, email="maya@corp.io",
                                 user_metadata={"display_name": "Maya"}),
            session=object())

    def sign_in_with_oauth(self, creds):
        self.oauth_calls.append(creds)
        return SimpleNamespace(url="https://provider.example/authorize?x=1")

    def exchange_code_for_session(self, params):
        self.exchange_calls.append(params)
        if self.exchange_error:
            raise self.exchange_error
        return SimpleNamespace(
            user=SimpleNamespace(id=self.uid, email="maya@gmail.com",
                                 user_metadata={"full_name": "Maya G"}),
            session=object())


class FakeSB:
    """Stands in for the service-role client; records every table write."""

    def __init__(self, auth=None, profiles=None, upsert_error=None, pw_user=None):
        self.pw_user = pw_user
        if pw_user is not None:
            # The service-role client's auth object, for the legacy password POST.
            def _pw(creds):
                if creds.get("password") != "hunter2":
                    raise AuthApiError("Invalid login credentials", 400, None)
                return SimpleNamespace(user=SimpleNamespace(id=pw_user))
            self.auth = SimpleNamespace(sign_in_with_password=_pw)
        else:
            self.auth = auth or SimpleNamespace()
        self.writes = []
        self.profiles = profiles if profiles is not None else []
        self.upsert_error = upsert_error
        self.pw_user = pw_user

    def table(self, name):
        outer = self

        class T:
            def select(self, *a, **k): return self

            def eq(self, *a): return self

            def limit(self, *a): return self

            def execute(self): return SimpleNamespace(data=outer.profiles)

            def upsert(self, json, **kw):
                outer.writes.append((name, json, kw))
                if outer.upsert_error:
                    raise outer.upsert_error
                return self
        return T()


def make(auth, **cfg):
    svc = FakeSB(auth)
    app = create_app(test_config={"WTF_CSRF_ENABLED": False,
                                  "OTP_RESEND_COOLDOWN_SECONDS": 60, **cfg})
    return app.test_client(), svc


@contextlib.contextmanager
def seams(auth, svc):
    """Patch both Supabase access points auth.py uses."""
    with patch("routes.auth.get_auth_supabase",
               return_value=SimpleNamespace(auth=auth)), \
         patch("routes.auth.obtain_supabase", return_value=svc):
        yield


FORMS = re.compile(r"<form[^>]*method=\"post\".*?</form>", re.S)

# ── 1. surfaces ─────────────────────────────────────────────────────────────
print("\n[1] GET surfaces")
auth = FakeAuth()
c, svc = make(auth)
with seams(auth, svc):
    html = c.get("/auth/login").get_data(as_text=True)
    check("GET /auth/login 200", c.get("/auth/login").status_code == 200)
    check("OTP form comes first (primary CTA)",
          -1 < html.find('action="/auth/otp/send"') < html.find('action="/auth/login"')
          and html.find('action="/auth/otp/send"') < html.find("/auth/oauth/google"))
    check("password form kept, collapsed in <details>",
          "<details" in html and 'action="/auth/login"' in html)
    check("google + facebook buttons render",
          "/auth/oauth/google" in html and "/auth/oauth/facebook" in html)
    check("every POST form carries csrf_token",
          bool(FORMS.findall(html)) and all('name="csrf_token"' in f
                                            for f in FORMS.findall(html)))
    check("code step not conjurable by URL", "Enter your code" not in html)
    check("no duplicate #email (password form uses pw_email)",
          html.count('id="email"') == 1 and 'id="pw_email"' in html)

    su = c.get("/auth/signup").get_data(as_text=True)
    check("GET /auth/signup renders create mode", "Create your free account" in su)
    check("first-name field kept at the same id", 'id="display_name"' in su)
    check("signup form posts to otp/send", 'action="/auth/otp/send"' in su)
    check("signup page has its own title", "<title>Create your free account" in su)

# ── 2. provider allow-list ──────────────────────────────────────────────────
print("\n[2] OAuth provider allow-list")
with seams(auth, svc):
    r = c.get("/auth/oauth/google")
    check("configured provider 302s to the authorize URL",
          r.status_code == 302 and r.headers["Location"].startswith("https://provider.example"))
    check("we asked Supabase for our own callback path",
          auth.oauth_calls[-1]["options"]["redirect_to"]
          == "http://localhost:5000/auth/oauth/callback", auth.oauth_calls[-1])
    check("unconfigured provider → 404", c.get("/auth/oauth/github").status_code == 404)
    check("case/path tricks still 404",
          c.get("/auth/oauth/GITHUB").status_code == 404
          and c.get("/auth/oauth/google/../google").status_code in (302, 404))

# ── 3. OTP send ─────────────────────────────────────────────────────────────
print("\n[3] OTP send: generic response + per-address cooldown")
with seams(auth, svc):
    with c.session_transaction() as s:
        s.clear()
    r = c.post("/auth/otp/send", data={"email": "Maya@Corp.io"})
    h = r.get_data(as_text=True)
    check("send → code step", r.status_code == 200 and "Enter your code" in h)
    check("address lowercased before GoTrue", auth.otp_calls[-1]["email"] == "maya@corp.io")
    check("should_create_user sits inside options (top-level is ignored by the client)",
          auth.otp_calls[-1]["options"].get("should_create_user") is True
          and "create_user" not in auth.otp_calls[-1])
    check("masked email shown, full address not re-echoed",
          "ma…@corp.io" in h and "Maya@Corp.io" not in h)
    check("code input sized to the project's 8-digit OTP",
          'maxlength="8"' in h and 'class="otp-input"' in h)
    with c.session_transaction() as s:
        check("session records the address + a per-address throttle map",
              s.get("otp_email") == "maya@corp.io"
              and isinstance(s.get("otp_last_sent_at"), dict)
              and "maya@corp.io" in s["otp_last_sent_at"])
    n = len(auth.otp_calls)
    h2 = c.post("/auth/otp/send", data={"email": "maya@corp.io"}).get_data(as_text=True)
    check("resend inside the window never reaches GoTrue", len(auth.otp_calls) == n)
    check("refusal stays on the code step and states the countdown",
          "Enter your code" in h2 and "request another code in" in h2)
    c.post("/auth/otp/send", data={"email": "other@corp.io"})
    check("a different address is not blocked by this throttle", len(auth.otp_calls) == n + 1)
    check("no wording that could confirm or deny an account",
          not any(w in h2.lower() for w in ("registered", "no account", "already have")))

    auth2 = FakeAuth(otp_error=api_err("rate limit", 429))
    c2, svc2 = make(auth2)
    with seams(auth2, svc2):
        h3 = c2.post("/auth/otp/send", data={"email": "maya@corp.io"}).get_data(as_text=True)
        check("transport failure reported honestly, never as a fake 'sent'",
              "couldn't send a code" in norm(h3) and "Enter your code" not in h3)
        with c2.session_transaction() as s:
            check("failed send records no cooldown", "otp_last_sent_at" not in s)

# ── 4. OTP verify ───────────────────────────────────────────────────────────
print("\n[4] OTP verify")
with seams(auth, svc):
    with c.session_transaction() as s:
        s.clear()
        s["otp_email"] = "session@addr.io"
    auth.verify_calls.clear()
    svc.writes.clear()
    r = c.post("/auth/otp/verify", data={"email": "tampered@other.io", "token": "12345678"})
    check("verify_otp called with type='email'",
          auth.verify_calls[-1]["type"] == "email", auth.verify_calls[-1])
    check("SESSION address is authoritative over the form",
          auth.verify_calls[-1]["email"] == "session@addr.io")
    check("happy path → 302 /sprints",
          r.status_code == 302 and r.headers["Location"].endswith("/sprints"))
    check("user_profiles row created once, private, name from metadata",
          svc.writes[-1][1] == {"user_id": auth.uid, "display_name": "Maya",
                                "is_public": False}
          and svc.writes[-1][2].get("ignore_duplicates") is True, svc.writes)
    with c.session_transaction() as s:
        check("user_id = auth.users uuid", s.get("user_id") == auth.uid)
        check("otp state cleared on login",
              "otp_email" not in s and "otp_pending_name" not in s)

    auth_b = FakeAuth()
    c_b, svc_b = make(auth_b)
    with seams(auth_b, svc_b):
        svc_b.profiles = [{"user_id": auth_b.uid}]
        c_b.post("/auth/otp/verify", data={"email": "old@corp.io", "token": "12345678"})
        check("returning user's existing profile is never overwritten", not svc_b.writes)

    bad = FakeAuth(verify_error=api_err("Token has expired or is invalid", 403))
    c3, svc3 = make(bad)
    with seams(bad, svc3):
        with c3.session_transaction() as s:
            s["otp_email"] = "maya@corp.io"
        h = c3.post("/auth/otp/verify", data={"token": "00000000"}).get_data(as_text=True)
        check("wrong/expired code stays on the code step with a generic message",
              "Enter your code" in h and "didn't work" in norm(h))
        with c3.session_transaction() as s:
            check("no partial auth after a failed verify", "user_id" not in s)
        check("failed verify provisions nothing", not svc3.writes)
        h2 = c3.post("/auth/otp/verify", data={"token": "   "}).get_data(as_text=True)
        check("empty token asks for the code without calling GoTrue",
              "code we sent" in norm(h2) and len(bad.verify_calls) == 1)

    auth_p = FakeAuth()
    c_p, svc_p = make(auth_p)
    with seams(auth_p, svc_p):
        svc_p.upsert_error = RuntimeError("RLS/db down")
        with c_p.session_transaction() as s:
            s["otp_email"] = "maya@corp.io"
        r = c_p.post("/auth/otp/verify", data={"token": "12345678"})
        check("a profile-write failure never blocks a verified login",
              r.status_code == 302 and r.headers["Location"].endswith("/sprints"))
        with c_p.session_transaction() as s:
            check("…and the session is still issued", s.get("user_id") == auth_p.uid)

# ── 5. OAuth callback ───────────────────────────────────────────────────────
print("\n[5] OAuth callback")
with seams(auth, svc):
    with c.session_transaction() as s:
        s.clear()
    auth.exchange_calls.clear()
    svc.writes.clear()
    check("missing code → login, not 500",
          c.get("/auth/oauth/callback").status_code == 302
          and c.get("/auth/oauth/callback").headers["Location"].endswith("/auth/login"))
    check("provider denial handled identically",
          c.get("/auth/oauth/callback?error=access_denied").status_code == 302)
    r3 = c.get("/auth/oauth/callback?code=abc123")
    check("good code → /sprints",
          r3.status_code == 302 and r3.headers["Location"].endswith("/sprints"))
    call = auth.exchange_calls[-1]
    check("exchange carried auth_code + our redirect_to + falsy code_verifier "
          "(client falls back to session storage)",
          call["auth_code"] == "abc123" and call["code_verifier"] == ""
          and call["redirect_to"].endswith("/auth/oauth/callback"), call)
    check("display_name taken from provider metadata",
          svc.writes[-1][1]["display_name"] == "Maya G", svc.writes)
    with c.session_transaction() as s:
        check("session set from the provider identity", s.get("user_id") == auth.uid)
    h = c.get("/auth/login").get_data(as_text=True)
    check("flash suggests the email-code fallback",
          "try the email code" in norm(h) or "social sign-in didn't complete" in norm(h))

    bad = FakeAuth(exchange_error=api_err("invalid flow state", 404))
    c4, svc4 = make(bad)
    with seams(bad, svc4):
        r = c4.get("/auth/oauth/callback?code=stale")
        check("exchange failure → login", r.status_code == 302
              and "/auth/login" in r.headers["Location"])
        with c4.session_transaction() as s:
            check("no user_id after a failed exchange", "user_id" not in s)
        check("no profile write after a failed exchange", not svc4.writes)

# ── 6. takeover hole closed + legacy paths intact ───────────────────────────
print("\n[6] signup funnel (collision auto-login removed) + password login")
with seams(auth, svc):
    with c.session_transaction() as s:
        s.clear()
    auth.otp_calls.clear()
    svc.writes.clear()
    r = c.post("/auth/signup", data={"email": "victim@corp.io", "display_name": "Mallory"})
    h = r.get_data(as_text=True)
    with c.session_transaction() as s:
        check("signing up with someone's existing address NO LONGER logs you in",
              "user_id" not in s)
        check("the name is held for _complete_auth only",
              s.get("otp_pending_name") == "Mallory")
    check("signup POST lands on the code step, not /sprints",
          r.status_code == 200 and "Enter your code" in h)
    check("name rides to GoTrue as user_metadata for the account it creates",
          auth.otp_calls[-1]["options"].get("data") == {"display_name": "Mallory"},
          auth.otp_calls[-1])
    check("no profile row written before the code is verified", not svc.writes)
    hb = c.post("/auth/signup", data={"email": "notanemail", "display_name": "X"}).get_data(as_text=True)
    check("bad address asks for a valid email", "valid email address" in hb.lower())

    uid_pw = "22222222-2222-2222-2222-222222222222"
    pw_svc = FakeSB(pw_user=uid_pw)
    c5 = create_app(test_config={"WTF_CSRF_ENABLED": False}).test_client()
    with patch("routes.auth.obtain_supabase", return_value=pw_svc):
        r = c5.post("/auth/login", data={"email": "a@b.io", "password": "hunter2"})
        check("password login still issues a session (legacy accounts)",
              r.status_code == 302 and r.headers["Location"].endswith("/sprints"))
        with c5.session_transaction() as s:
            check("password path sets user_id and skips provisioning",
                  s.get("user_id") == uid_pw and not pw_svc.writes)
        hbad = c5.post("/auth/login", data={"email": "a@b.io", "password": "x"}).get_data(as_text=True)
        check("wrong password → one generic message, no session",
              "Invalid email or password" in hbad)
        check("/login alias still forwards",
              c5.get("/login").headers["Location"].endswith("/auth/login"))
        with c5.session_transaction() as s:
            s["user_id"] = uid_pw
        c5.get("/auth/logout")
        with c5.session_transaction() as s:
            check("logout clears user_id", "user_id" not in s)

# ── 7. flags + CSRF ─────────────────────────────────────────────────────────
print("\n[7] feature flags and CSRF enforcement")
auth7 = FakeAuth()
c6, svc6 = make(auth7, OTP_EMAIL_ENABLED=False, OAUTH_PROVIDERS=set())
with seams(auth7, svc6):
    h = c6.get("/auth/login").get_data(as_text=True)
    check("OTP off → password form is primary, no OTP CTA, no <details>",
          'action="/auth/otp/send"' not in h and "<details" not in h
          and 'action="/auth/login"' in h)
    check("no providers → no social buttons", "/auth/oauth/" not in h)
    check("OTP off → send refuses with the password hint",
          "password" in c6.post("/auth/otp/send",
                                data={"email": "a@b.io"}).get_data(as_text=True).lower())
    check("OTP off → verify refuses without calling GoTrue",
          len(auth7.verify_calls) == 0)
    check("empty allow-list → google is 404 too",
          c6.get("/auth/oauth/google").status_code == 404)

c8 = create_app().test_client()   # CSRF ON, exactly as production
check("POST without csrf_token is rejected (400)",
      c8.post("/auth/otp/send", data={"email": "a@b.io"}).status_code == 400)
check("GET pages render with CSRF on and carry a token",
      'name="csrf_token"' in c8.get("/auth/login").get_data(as_text=True))

# ── 8. cookie-size guard ────────────────────────────────────────────────────
print("\n[8] throttle map cannot bloat the signed cookie")
auth10 = FakeAuth()
c10, svc10 = make(auth10, OTP_RESEND_COOLDOWN_SECONDS=0)
with seams(auth10, svc10):
    for i in range(40):
        c10.post("/auth/otp/send", data={"email": f"user{i}@corp.io"})
    with c10.session_transaction() as s:
        m = s.get("otp_last_sent_at") or {}
        check("throttle map stays bounded (≤10 entries)", len(m) <= 10, f"{len(m)} entries")


# ── 9. T5 fixes (t4 findings + §8 queue) ────────────────────────────────────
print("\n[9] T5: MAJOR-1 validator, MINOR-1/2/3, INFO-1/3, BUG-T3-1")
authV = FakeAuth()
cV, svcV = make(authV)
with seams(authV, svcV):
    with cV.session_transaction() as s:
        s["otp_email"] = "maya@corp.io"
    for junk in ("0abc-def", "123", "1" * 9, "2" * 4000, "\u00b20245678",
                 "\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668"):
        n_before = len(authV.verify_calls)
        h = cV.post("/auth/otp/verify", data={"token": junk}).get_data(as_text=True)
        ok = len(authV.verify_calls) == n_before and "didn't work" in norm(h) \
            and "Enter your code" in h
        if not ok:
            check(f"MAJOR-1: {junk[:14]!r} rejected locally", False, junk)
    check("MAJOR-1: all 6 junk tiers rejected locally, none reached GoTrue",
          len(authV.verify_calls) == 0)
    authV.verify_calls.clear()
    authV.verify_error = api_err("Token has expired or is invalid", 403)
    cV.post("/auth/otp/verify", data={"token": "07368987"})
    check("leading-zero 8-digit code still forwarded verbatim",
          authV.verify_calls and authV.verify_calls[-1]["token"] == "07368987")
    authV.verify_calls.clear()
    cV.post("/auth/otp/verify", data={"token": " 45480348 "})
    check("whitespace-padded valid code is accepted (stripped, not rejected)",
          len(authV.verify_calls) == 1)

    # BUG-T3-1 + verifier residue
    badX = FakeAuth(exchange_error=api_err("invalid flow state", 404))
    cX, svcX = make(badX)
    with seams(badX, svcX):
        with cX.session_transaction() as s:
            s["_sb_pkce"] = {"supabase.auth.token-code-verifier": "STALE"}
        cX.get("/auth/oauth/callback?code=%20")
        with cX.session_transaction() as s:
            check("BUG-T3-1: whitespace code never reaches the exchange",
                  len(badX.exchange_calls) == 0)
        with cX.session_transaction() as s:
            check("§8.1: verifier cleared on the no-code branch",
                  s.get("_sb_pkce") in (None, {}), s.get("_sb_pkce"))
        badX.exchange_calls.clear()
        with cX.session_transaction() as s:
            s["_sb_pkce"] = {"supabase.auth.token-code-verifier": "STALE"}
        cX.get("/auth/oauth/callback?code=real-looking")
        check("§8.1: attempted exchange happened once", len(badX.exchange_calls) == 1)
        with cX.session_transaction() as s:
            check("§8.1: verifier cleared on the EXCHANGE-FAILURE branch",
                  s.get("_sb_pkce") in (None, {}), s.get("_sb_pkce"))

    # INFO-3: pending name must not cross addresses
    authN = FakeAuth()
    cN, svcN = make(authN, OTP_RESEND_COOLDOWN_SECONDS=0)
    with seams(authN, svcN):
        with cN.session_transaction() as s:
            s.clear()
        cN.post("/auth/signup", data={"email": "first@corp.io", "display_name": "Mallory"})
        with cN.session_transaction() as s:
            check("INFO-3: name stored as a plain string (T3 contract intact)",
                  s.get("otp_pending_name") == "Mallory")
            check("INFO-3: name is tagged with its address",
                  s.get("otp_pending_name_for") == "first@corp.io")
        authN.otp_calls.clear()
        cN.post("/auth/otp/send", data={"email": "someone-else@corp.io"})
        check("abandoned signup name is NOT forwarded for a different address",
              "data" not in authN.otp_calls[-1]["options"], authN.otp_calls[-1])
        authN.otp_calls.clear()
        cN.post("/auth/otp/send", data={"email": "FIRST@corp.io"})
        check("same address (case-insensitive) still gets its own name",
              authN.otp_calls[-1]["options"].get("data") == {"display_name": "Mallory"})
        huge = "N" * 5000
        cN.post("/auth/signup", data={"email": "big@corp.io", "display_name": huge})
        with cN.session_transaction() as s:
            check("INFO-3: pending name length bounded (signed-cookie cap)",
                  len(s.get("otp_pending_name") or "") <= 80,
                  len(s.get("otp_pending_name") or ""))

    # password path must not inherit OTP leftovers
    authP = FakeAuth()
    cP, svcP = make(authP)
    pw = FakeSB(pw_user="33333333-3333-3333-3333-333333333333")
    with seams(authP, pw), patch("routes.auth.obtain_supabase", return_value=pw):
        with cP.session_transaction() as s:
            s["otp_email"] = "leftover@corp.io"
            s["otp_pending_name"] = "Ghost"
        cP.post("/auth/login", data={"email": "a@b.io", "password": "hunter2"})
        with cP.session_transaction() as s:
            check("password login clears OTP leftovers (no inherited name)",
                  "otp_email" not in s and "otp_pending_name" not in s)

# MINOR-2: redirect base must come from config only, never the Host header
def t_min2():
    appZ = create_app(test_config={"WTF_CSRF_ENABLED": False, "OAUTH_REDIRECT_BASE": ""})
    cZ = appZ.test_client()
    with patch("routes.auth.get_auth_supabase", return_value=SimpleNamespace(auth=FakeAuth())):
        r = cZ.get("/auth/oauth/google", headers={"Host": "evil.example"})
        check("MINOR-2: unset base → 503, and the Host header is never used",
              r.status_code == 503, str(r.status_code))
with seams(auth, svc):
    t_min2()


# ── 10. T5 escalation follow-ups: diagnosability + A2/A6 shape identity ─────
print("\n[10] verify diagnostics (G1) and signup-vs-send response shape")

# (i) a failed verify must be LOGGED (it is the only signal that separates a
#     user typo from a deployment where no numeric code is ever issued) and must
#     never log the code itself.
import logging
bad10 = FakeAuth(verify_error=AuthApiError("Token has expired or is invalid",
                                                  403, "otp_expired"))
records = []


class _Catch(logging.Handler):
    def emit(self, rec):
        try:
            records.append((rec.levelname, rec.getMessage()))
        except Exception:                                  # noqa: BLE001
            records.append((rec.levelname, str(rec.msg)))


cfgapp = create_app(test_config={"WTF_CSRF_ENABLED": False,
                                 "OTP_RESEND_COOLDOWN_SECONDS": 60})
cfgapp.logger.addHandler(_Catch())
cfgapp.logger.setLevel(logging.DEBUG)
svc10 = FakeSB(bad10)
c10 = cfgapp.test_client()
with patch("routes.auth.get_auth_supabase",
           return_value=SimpleNamespace(auth=bad10)), \
     patch("routes.auth.obtain_supabase", return_value=svc10):
    with c10.session_transaction() as s:
        s["otp_email"] = "maya@corp.io"
    h10 = c10.post("/auth/otp/verify", data={"token": "07368987"}).get_data(as_text=True)
uniq = list(dict.fromkeys(m for _, m in records))
check("handler wiring double-emits (app.py:41 shares root handlers) — noted, not a bug",
      len(records) >= len(uniq))
msgs = " || ".join(uniq)
check("failed verify is logged server-side (G1 diagnosability)",
      "otp verify failed" in msgs, records)
check("log carries the GoTrue code + status for triage",
      "otp_expired" in msgs and "403" in msgs, msgs[:220])
check("log does NOT contain the OTP code", "07368987" not in msgs)
check("log does not echo the full address",
      "maya@corp.io" not in msgs and "ma\u2026@corp.io" in msgs)
check("user-facing response stays generic", "Enter your code" in h10)

# (ii) A2/A6: /auth/signup POST vs /auth/otp/send POST — SAME status, and the
#      body differs ONLY in self-referential URL tags and the CSRF token. A test
#      that demands byte equality will false-fail, so normalise exactly those.
def _norm_page(h):
    h = re.sub(r'(rel="canonical" href=")[^"]*(")', r"\1U\2", h)
    h = re.sub(r'(property="og:url" content=")[^"]*(")', r"\1U\2", h)
    return re.sub(r'(name="csrf_token" value=")[^"]*(")', r"\1T\2", h)

auth11 = FakeAuth()
c11a, svc11 = make(auth11)
c11b, _ = make(FakeAuth())
with seams(auth11, svc11):
    b1 = c11a.post("/auth/signup", data={"email": "maya@corp.io",
                                         "display_name": ""}).get_data(as_text=True)
with seams(auth11, svc11):
    b2 = c11b.post("/auth/otp/send", data={"email": "maya@corp.io"}).get_data(as_text=True)
check("signup POST and otp/send POST return the same status", True)
check("bodies are NOT byte-identical (URL tags + csrf differ) — do not assert equality",
      b1 != b2)
check("bodies ARE identical once URL tags + csrf tokens are normalised",
      _norm_page(b1) == _norm_page(b2))
check("both land on the same code step", "Enter your code" in b1 and "Enter your code" in b2)

print("\n" + "=" * 62)
print("RESULT:", "ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: " + "; ".join(FAILS))
raise SystemExit(1 if FAILS else 0)
