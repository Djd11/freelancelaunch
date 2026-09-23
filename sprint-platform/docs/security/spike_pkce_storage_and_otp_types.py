"""Spike evidence for spec §5.1 / §5.2 (branch feature/passwordless-otp-social-login).

Answers, with runnable proof rather than opinion:
  A. What is the *exact* storage protocol supabase-auth 2.31.0 calls, and does a
     duck-typed get/set/delete object survive it? (spec §5.1 says "get/set/delete")
  B. Is `flow_type` already "pkce" by default in SyncClientOptions?
  C. Which `type` literals does the live GoTrue /verify endpoint accept for an
     8-digit email code (Magic-link template carrying {{ .Token }})?  NOTE: codes
     on this project are 8 digits, not the 6 the design spec says, and ~1 in 10
     begin with a leading zero — the token must stay a string end to end.

Safety: Part A/B are pure local (sign_in_with_oauth only builds a URL — no HTTP).
Part C calls /verify with a deliberately bogus code: it sends NO email, creates NO
user, and consumes no SMTP quota. Do not run docs/dogfood/probe_gotrue_otp.py —
that one POSTs /otp and actually sends mail on the ~2/hr built-in SMTP.

Run: .venv/bin/python docs/security/spike_pkce_storage_and_otp_types.py
"""
import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

BASE = (os.getenv("SUPABASE_URL") or "").strip()
ANON = (os.getenv("SUPABASE_ANON_KEY") or "").strip()


def section(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


# ---------------------------------------------------------------- Part A/B ----
def probe_storage_protocol():
    from supabase import create_client
    from supabase.lib.client_options import SyncClientOptions
    from supabase_auth import SyncSupportedStorage

    print("SyncSupportedStorage abstract methods:",
          sorted(SyncSupportedStorage.__abstractmethods__))

    # 1. The shape spec §5.1 literally describes: duck-typed get/set/delete.
    class SpecShapedDuck:
        def __init__(self):
            self.d = {}

        def get(self, key):
            return self.d.get(key)

        def set(self, key, value):
            self.d[key] = value

        def delete(self, key):
            self.d.pop(key, None)

    # 2. Subclass of the ABC but with the spec's method names.
    class SpecShapedSubclass(SyncSupportedStorage):
        def __init__(self):
            self.d = {}

        def get(self, key):
            return self.d.get(key)

        def set(self, key, value):
            self.d[key] = value

        def delete(self, key):
            self.d.pop(key, None)

    # 3. The candidate correct shape: get_item/set_item/remove_item, no subclass.
    class ItemShapedDuck:
        def __init__(self):
            self.d = {}

        def get_item(self, key):
            return self.d.get(key)

        def set_item(self, key, value):
            self.d[key] = value

        def remove_item(self, key):
            self.d.pop(key, None)

    # 4. Same, subclassing the ABC.
    class ItemShapedSubclass(SyncSupportedStorage):
        def __init__(self):
            self.d = {}

        def get_item(self, key):
            return self.d.get(key)

        def set_item(self, key, value):
            self.d[key] = value

        def remove_item(self, key):
            self.d.pop(key, None)

    for label, factory in (
        ("spec §5.1 duck-typed get/set/delete", SpecShapedDuck),
        ("spec §5.1 subclass w/ get/set/delete", SpecShapedSubclass),
        ("get_item/set_item/remove_item (duck)", ItemShapedDuck),
        ("get_item/set_item/remove_item (ABC subclass)", ItemShapedSubclass),
    ):
        try:
            storage = factory()
            opts = SyncClientOptions(flow_type="pkce", storage=storage,
                                     persist_session=False, auto_refresh_token=False)
            sb = create_client(BASE or "https://x.supabase.co", ANON or "anon",
                               options=opts)
            # sign_in_with_oauth performs NO network call: it only builds the URL
            # and (pkce) writes the code verifier into storage.
            res = sb.auth.sign_in_with_oauth({"provider": "google"})
            keys = list(storage.d.keys())
            ok = any(k.endswith("-code-verifier") for k in keys)
            print(f"  [{label}]")
            print(f"      client built + sign_in_with_oauth OK; "
                  f"verifier stored={ok}; storage keys={keys}")
            print(f"      is_pkce_flow storage_key={sb.auth._storage_key!r} "
                  f"flow={sb.auth._flow_type!r}")
            if not ok:
                print("      >>> FAIL: verifier did not land in storage")
        except Exception as exc:
            print(f"  [{label}]")
            print(f"      >>> {type(exc).__name__}: {exc}")

    section("B. default flow_type on the plain create_client() path")
    plain = create_client(BASE or "https://x.supabase.co", ANON or "anon")
    print("  get_supabase()/get_client_supabase() clients today: "
          f"flow={plain.auth._flow_type!r} "
          f"persist_session={plain.auth._persist_session!r} "
          f"auto_refresh_token={plain.auth._auto_refresh_token!r} "
          f"storage={type(plain.auth._storage).__name__}")


# ----------------------------------------------------------------- Part C -----
def probe_verify_types():
    if not (BASE and ANON):
        print("  SKIP: SUPABASE_URL / SUPABASE_ANON_KEY not set")
        return
    url = BASE.rstrip("/") + "/auth/v1/verify"
    headers = {
        "apikey": ANON,
        "Authorization": f"Bearer {ANON}",
        "Content-Type": "application/json",
        "X-Client-Info": "supabase-py/security-spike",
    }
    # Never a real mailbox: the point is the *type* discriminator, not delivery.
    probe_email = "sec-spike-probe@example.com"
    for t in ("email", "signup", "magiclink", "recovery", "totally-bogus"):
        body = {"email": probe_email, "token": "000000", "type": t}
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                out = r.read()[:300].decode("utf-8", "replace")
                print(f"  type={t!r:<14} HTTP {r.status} {out}")
        except urllib.error.HTTPError as e:
            out = e.read()[:300].decode("utf-8", "replace")
            print(f"  type={t!r:<14} HTTP {e.code} {out}")
        except Exception as exc:  # noqa: BLE001
            print(f"  type={t!r:<14} ERR {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    section("A. supabase-auth 2.31.0 storage protocol actually invoked by PKCE")
    probe_storage_protocol()
    section("C. live GoTrue: which verify `type` literal accepts an email code")
    probe_verify_types()
