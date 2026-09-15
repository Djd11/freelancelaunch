"""Spike T1 — part B: LIVE probe against the configured Supabase project.

Run from the repo root:  .venv/bin/python docs/superpowers/spikes/spike_live.py
Reads .env. NEVER prints a secret. Side effects it creates (recorded in the
printed SUMMARY for cleanup):
  * one auth.users row for a throwaway `.invalid` address (undeliverable TLD,
    RFC 6761 — no mail can ever reach a real person)
  * one OTP email send attempt (counts against the project's hourly rate limit)
"""
import json
import time
import traceback

from flask import Flask, session

from supabase import create_client
from supabase_auth import SyncSupportedStorage
from supabase_auth.errors import AuthApiError, AuthError

from dotenv import dotenv_values

ENV = dotenv_values(".env")
URL = (ENV.get("SUPABASE_URL") or "").strip()
ANON = (ENV.get("SUPABASE_ANON_KEY") or ENV.get("SUPABASE_KEY") or "").strip()
print(f"URL={URL}  anon key present={bool(ANON)} (len {len(ANON)})")

STORAGE_KEY = "supabase.auth.token"


class FlaskSessionStorage(SyncSupportedStorage):
    """Candidate implementation for §5.1 — stores under flask.session['_sb_pkce'].

    Reassigns the whole sub-dict on every write because mutating a nested dict
    does not set flask.session.modified (Flask 3.1 skips the Set-Cookie).
    """

    def __init__(self, storage_key=STORAGE_KEY):
        self.storage_key = storage_key
        self.log = []

    def _bucket(self):
        b = session.get("_sb_pkce")
        if not isinstance(b, dict):
            b = {}
            session["_sb_pkce"] = b
        return b

    def get_item(self, key):
        self.log.append(("get", key))
        v = self._bucket().get(key)
        return v

    def set_item(self, key, value):
        self.log.append(("set", key))
        b = dict(self._bucket())
        b[key] = value
        session["_sb_pkce"] = b
        session.modified = True

    def remove_item(self, key):
        self.log.append(("del", key))
        b = dict(self._bucket())
        b.pop(key, None)
        session["_sb_pkce"] = b
        session.modified = True


app = Flask(__name__)
app.config["SECRET_KEY"] = "spike-only"

TS = int(time.time())
EMAIL = f"spike.t1.{TS}@sprint.invalid"
CREATED_UID = None

with app.test_request_context("/auth/login"):
    storage = FlaskSessionStorage()
    sb = create_client(
        URL,
        ANON,
        options=__import__("supabase").ClientOptions(
            flow_type="pkce",
            storage=storage,
            persist_session=False,
            auto_refresh_token=False,
        ),
    )
    auth = sb.auth
    print(f"auth client class={type(auth).__name__} flow={auth._flow_type} "
          f"persist={auth._persist_session} storage={type(auth._storage).__name__} "
          f"storage_key={auth._storage_key}")

    # ---- L1: server settings (read-only) — providers + mail config ----------
    print("\n=== L1  GET /auth/v1/settings ===")
    try:
        s = auth._request("GET", "settings")
        keep = {k: s.get(k) for k in (
            "external", "mailer_autoconfirm", "disable_signup", "site_url",
            "uri_allow_list", "otp_exp", "otp_length", "security",
            "smtp_admin", "mailer_secure_email_change_enabled")}
        print(json.dumps(keep, indent=1, default=str)[:1600])
    except Exception as e:
        print("settings failed:", type(e).__name__, e)

    # ---- L2: sign_in_with_otp for the throwaway email -----------------------
    print("\n=== L2  sign_in_with_otp({email, should_create_user:true}) ===")
    otp_res = None
    try:
        # NOTE: the email branch builds a strict allow-list body
        # {email, data, create_user, gotrue_meta_security}; a top-level
        # "create_user" key is IGNORED. should_create_user must come from options.
        otp_res = auth.sign_in_with_otp({
            "email": EMAIL,
            "options": {"should_create_user": True},
        })
        print("type:", type(otp_res).__name__)
        print("repr fields:", [a for a in dir(otp_res) if not a.startswith("_")])
        print("is_signup_enabled:", getattr(otp_res, "is_signup_enabled", "MISSING"))
        print("user_id:", getattr(otp_res, "user_id", "MISSING"))
        u = getattr(otp_res, "user", None)
        print("user:", None if u is None else (u.id, u.email, u.email_confirmed_at))
        print("session is None:", getattr(otp_res, "session", "MISSING") is None)
    except (AuthApiError, AuthError) as e:
        print(f"RAISED {type(e).__name__}: message={getattr(e,'message',None)!r} "
              f"status={getattr(e,'status','')} code={getattr(e,'code','')} "
              f"headers_present={bool(getattr(e,'headers',None))}")
        traceback.print_exc()
    except Exception as e:
        print("RAISED unexpected", type(e).__name__, e)
        traceback.print_exc()

    # ---- L3: verify_otp with the spec's type="email", bogus code ------------
    print('\n=== L3  verify_otp({email, token:"000000", type:"email"}) ===')
    try:
        r = auth.verify_otp({"email": EMAIL, "token": "000000", "type": "email"})
        print("returned:", type(r).__name__,
              "user:", getattr(getattr(r, "user", None), "id", None))
    except (AuthApiError, AuthError) as e:
        print(f"RAISED {type(e).__name__}: message={getattr(e,'message',None)!r} status={getattr(e,'status','')}")
        msg = (getattr(e, "message", "") or "").lower()
        print("=> 'email' literal REJECTED?" ,
              "invalid type" in msg or "bad request" in msg and "type" in msg)
    except Exception as e:
        print("RAISED unexpected", type(e).__name__, e)

    # ---- L4: control — a deliberately bogus type literal --------------------
    print('\n=== L4  control: same call with type="bogus_type" ===')
    try:
        auth.verify_otp({"email": EMAIL, "token": "000000", "type": "bogus_type"})
        print("returned without error (server ignored the type!)")
    except (AuthApiError, AuthError) as e:
        print(f"RAISED {type(e).__name__}: message={getattr(e,'message',None)!r} status={getattr(e,'status','')}")

    # ---- L5: PKCE plumbing through FlaskSessionStorage ----------------------
    print("\n=== L5  sign_in_with_oauth → verifier in flask.session ===")
    oauth = auth.sign_in_with_oauth({"provider": "google", "options": {
        "redirect_to": "http://localhost:5000/auth/oauth/callback"}})
    print("url:", oauth.url)
    print("storage log:", storage.log)
    print("flask.session['_sb_pkce'] keys:", list(session.get("_sb_pkce", {})))
    print("session.modified:", session.modified)

    print("\n=== L6  exchange with a bogus code (proves verifier lookup) ===")
    try:
        auth.exchange_code_for_session({
            "auth_code": "bogus-code-for-spike",
            "code_verifier": "bogus-verifier",
            "redirect_to": "http://localhost:5000/auth/oauth/callback"})
    except (AuthApiError, AuthError) as e:
        print(f"explicit verifier → {type(e).__name__}: {getattr(e,'message',None)!r} status={getattr(e,'status','')}")
    except Exception as e:
        print("explicit verifier → unexpected", type(e).__name__, e)
    try:
        auth.exchange_code_for_session({
            "auth_code": "bogus-code-for-spike",
            "code_verifier": None,
            "redirect_to": "http://localhost:5000/auth/oauth/callback"})
    except (AuthApiError, AuthError) as e:
        print(f"None verifier (storage fallback) → {type(e).__name__}: {getattr(e,'message',None)!r} status={getattr(e,'status','')}")
    except Exception as e:
        print("None verifier → unexpected", type(e).__name__, repr(e)[:200])
    print("storage log now:", storage.log)

    print("\n=== SUMMARY ===")
    print("throwaway email:", EMAIL)
    if otp_res is not None and getattr(otp_res, "user", None) is not None:
        CREATED_UID = otp_res.user.id
    print("created uid:", CREATED_UID)
