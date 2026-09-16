"""Spike T1 — part D: does the PKCE verifier survive a real cookie round-trip?

§1's trap #2 (Flask skipping Set-Cookie for nested-dict mutation) can only bite
across TWO requests, so a single test_request_context cannot catch it. This uses
a real test_client with a cookie jar and ad-hoc routes, and proves:

  1. request 1 (oauth start)  → Set-Cookie carries the verifier
  2. request 2 (callback-ish) → the SAME client instance reads it back
  3. after exchange          → the verifier key is gone
  4. two separate clients    → verifiers do NOT leak between users
"""
from flask import g, redirect, session, url_for

from app import create_app
from services.supabase_client import (get_auth_supabase, get_supabase,
                                      get_client_supabase)

app = create_app()
CALLBACK = app.config["OAUTH_REDIRECT_BASE"] + app.config["OAUTH_CALLBACK_PATH"]


@app.route("/_spike/oauth-start")
def _spike_start():
    auth = get_auth_supabase().auth
    res = auth.sign_in_with_oauth({"provider": "google",
                                   "options": {"redirect_to": CALLBACK}})
    return redirect(res.url)


@app.route("/_spike/oauth-read")
def _spike_read():
    auth = get_auth_supabase().auth
    key = f"{auth._storage_key}-code-verifier"
    return {"from_storage": auth._storage.get_item(key),
            "raw_bucket": session.get("_sb_pkce")}


@app.route("/_spike/oauth-clear")
def _spike_clear():
    auth = get_auth_supabase().auth
    auth._storage.remove_item(f"{auth._storage_key}-code-verifier")
    return {"ok": True}


c1 = app.test_client()
r1 = c1.get("/_spike/oauth-start")
set_cookie = r1.headers.get("Set-Cookie", "")
print("1) start status:", r1.status_code,
      "| authorize host:", r1.headers.get("Location", "")[:48], "...")
print("   Set-Cookie present:", bool(set_cookie), "| session cookie set:",
      "session=" in set_cookie)

r2 = c1.get("/_spike/oauth-read")
back = r2.get_json()
print("2) request 2 read back from its OWN session:",
      repr((back["from_storage"] or "")[:14]), "...")
print("   cross-request persistence WORKS:", bool(back["from_storage"]))

v1 = back["from_storage"]

# second, independent "user"
c2 = app.test_client()
c2.get("/_spike/oauth-start")
v2 = c2.get("/_spike/oauth-read").get_json()["from_storage"]
print("3) separate client got a DIFFERENT verifier (no cross-user leak):",
      bool(v1 and v2 and v1 != v2))

# snapshot the bucket while the flow is still open — the 1-key assertion below
# must not run after remove_item has emptied it (my first pass asserted on {})
bucket_live = c1.get("/_spike/oauth-read").get_json()["raw_bucket"] or {}
c1.get("/_spike/oauth-clear")
v1_after = c1.get("/_spike/oauth-read").get_json()["from_storage"]
print("4) after remove_item the key is gone:", v1_after is None,
      "| bucket left as:", c1.get("/_spike/oauth-read").get_json()["raw_bucket"])
print("   other user unaffected:",
      c2.get("/_spike/oauth-read").get_json()["from_storage"] == v2)

# 1-key assertion (captain T1 amendment #1): with persist_session=False the
# cookie must carry the verifier and NOTHING else — no session JSON, no refresh token.
keys = list(bucket_live)
print("6) exactly one key in storage:", len(keys) == 1, keys)
print("   key is the fixed verifier key:",
      keys == ["supabase.auth.token-code-verifier"])
val = next(iter(bucket_live.values()), "")
print("   value is a ~64-char urlsafe verifier:", len(val) == 64,
      "| no +/= chars:", all(ch not in val for ch in "+/="))
print("   cookie payload added by PKCE: ~%d bytes of the 4KB budget" % len(val))

# amendment #3: the two pre-existing clients must arm no refresh timer either.
import time as _t
from supabase_auth.types import Session, User
_now = _t.time()
_u = User(id="11111111-1111-1111-1111-111111111111", aud="authenticated",
          role="authenticated", email="probe@example.org", app_metadata={},
          user_metadata={}, created_at=_t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime(_now)))
with app.test_request_context("/"):
    for label, getter in (("get_supabase (service-role)", get_supabase),
                          ("get_client_supabase (anon)", get_client_supabase),
                          ("get_auth_supabase (pkce)", get_auth_supabase)):
        cl = getter()
        a = cl.auth
        print(f"7) {label:28s} persist={a._persist_session} auto={a._auto_refresh_token}", end="")
        sess = Session(access_token="a", token_type="bearer", expires_in=3600,
                       refresh_token="r", user=_u)
        sess.expires_at = int(_now) + 3600
        a._save_session(sess)   # what sign_in_with_password / verify_otp do internally
        armed = a._refresh_token_timer is not None
        print(f" -> daemon refresh timer armed: {armed}"
              + ("  <-- MUST BE False" if armed else ""))
        if armed:
            a._refresh_token_timer.cancel()

# teardown must close the auth client's httpx connection
with app.test_request_context("/"):
    from flask import g as _g
    from services.supabase_client import close_request_clients
    probe = get_auth_supabase()
    assert "auth_supabase" in _g
    close_request_clients()
    print("5) teardown pops auth_supabase:", "auth_supabase" not in _g,
          "| that client's httpx connection closed:",
          probe.auth._http_client.is_closed)
