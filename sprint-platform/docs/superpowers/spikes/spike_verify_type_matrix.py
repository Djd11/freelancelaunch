"""T5 escalation check, corrected matrix: which literals redeem a TRUE
signup-family token vs a magiclink-family token?

Why a second pass was needed: spike_verify_type_both_families.py called
generate_link once per address as a "probe" before redeeming, so by the time it
verified, the user ALREADY existed and GoTrue had minted a magiclink-family
token for all three "states" — which is why 'signup' 403'd everywhere and
contradicted my own T1 control run (where a first-ever mint, type='email'/'signup'
OK and 'magiclink' 403'd). Both observations were right; the label was wrong.

Isolating the real variable — was the user created BY this mint, or earlier?

  FAMILY 1 (signup):     the FIRST generate_link for an address that does not
                         exist yet creates the user and the token together.
  FAMILY 2 (magiclink):  any mint for an address that already exists.

One address per literal, so each literal is offered a token that has never been
touched, and a prior success can never consume it (a verify consumes on success).

Cleanup: deletes only the ids this run enumerated, then re-queries and reports
any unexplained delta.
"""
import time

from supabase import create_client
from dotenv import dotenv_values
from supabase_auth.errors import AuthApiError

E = dotenv_values(".env")
URL = E["SUPABASE_URL"].strip()
anon = create_client(URL, (E.get("SUPABASE_ANON_KEY") or E.get("SUPABASE_KEY")).strip())
svc = create_client(URL, E["SUPABASE_SERVICE_ROLE_KEY"].strip())

TS = int(time.time())
SUFFIX = "@sprintspike-otp.dev"
MADE = []
LITERALS = ("email", "signup", "magiclink", "recovery")


def snapshot():
    return {u.id for u in svc.auth.admin.list_users()}


BEFORE = snapshot()


def gen(email, typ="magiclink"):
    return svc.auth.admin._request(
        "POST", "admin/generate_link",
        body={"type": typ, "email": email, "password": None,
              "new_email": None, "data": None}).json()


def redeem(email, code, literal):
    try:
        r = anon.auth.verify_otp({"email": email, "token": code, "type": literal})
        return "OK" if r.user else "OK(nouser)"
    except AuthApiError as e:
        return f"403/{getattr(e, 'code', '') or e.status}"
    except Exception as e:                                     # noqa: BLE001
        return f"ERR/{type(e).__name__}"


try:
    print(f"auth.users before: {len(BEFORE)}")

    # ---- FAMILY 1: token minted in the same call that CREATES the user ------
    print("\n=== FAMILY 1 — signup-family token (first-ever mint for a new "
          "address; no prior probe) ===")
    f1 = {}
    for lit in LITERALS:
        addr = f"t5f1.{lit}.{TS}{SUFFIX}"       # a fresh address per literal
        body = gen(addr)
        uid = body.get("id")
        if uid:
            MADE.append(uid)
        code = str(body.get("email_otp"))
        f1[lit] = redeem(addr, code, lit)
        print(f"  type={lit!r:12s} verification_type="
              f"{body.get('verification_type')!r:10} code={code} -> {f1[lit]}")

    # ---- FAMILY 2: address already exists, so this mint is a confirmation ---
    print("\n=== FAMILY 2 — magiclink-family token (address created by an "
          "earlier mint) ===")
    f2 = {}
    for lit in LITERALS:
        addr = f"t5f2.{lit}.{TS}{SUFFIX}"
        seed = gen(addr)                          # creates the user
        if seed.get("id"):
            MADE.append(seed["id"])
        body = gen(addr)                          # now an existing user
        code = str(body.get("email_otp"))
        f2[lit] = redeem(addr, code, lit)
        print(f"  type={lit!r:12s} verification_type="
              f"{body.get('verification_type')!r:10} code={code} -> {f2[lit]}")

    print("\n" + "=" * 66)
    print("MATRIX (email+token verify shape — the shape routes/auth.py ships)")
    print(f"  {'literal':12s} {'signup-family':>16s} {'magiclink-family':>18s}")
    for lit in LITERALS:
        print(f"  {lit!r:12s} {f1[lit]:>16s} {f2[lit]:>18s}")
    ok_both = [lit for lit in LITERALS if f1[lit].startswith("OK")
               and f2[lit].startswith("OK")]
    print(f"\n  literals that redeem BOTH families: {ok_both}")
    print("  routes/auth.py pins \"email\" -> sufficient for both account "
          f"states: {'email' in ok_both}")
finally:
    print("\n=== CLEANUP (this run's enumerated ids only) ===")
    for uid in dict.fromkeys(MADE):
        try:
            svc.auth.admin.delete_user(uid)
            print("deleted", uid)
        except Exception as e:                                 # noqa: BLE001
            print("DELETE FAILED", uid, type(e).__name__, str(e)[:100])
    AFTER = snapshot()
    print("auth.users after:", len(AFTER))
    print("  created-but-left:", (AFTER - BEFORE) or "none")
    print("  pre-existing-now-gone:", (BEFORE - AFTER) or "none  <-- must be none")
