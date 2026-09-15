"""Spike T1 — part C (v2): SMTP-free OTP code round-trip + UNCONFOUNDED controls.

v1 bug: an email OTP is single-use, so verifying in step 2 consumed the token and
made every later "wrong type" control fail for the wrong reason. v2 spends ONE
fresh token per literal, so each result is attributable.

`admin.generate_link` returns the numeric code in the JSON body (field
`email_otp`), so no SMTP/dashboard config is needed to obtain a live code. The
response carries the user fields at TOP level (no nested "user" object), and
every id created here is deleted in `finally`.
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
MADE = []


def gen(email):
    """Fresh magiclink-style token; returns raw JSON (model drops token fields)."""
    return svc.auth.admin._request(
        "POST", "admin/generate_link",
        body={"type": "magiclink", "email": email, "password": None,
              "new_email": None, "data": None},
    ).json()


def try_literal(tag, literal):
    """One throwaway address + one fresh token per literal: no reuse confound."""
    email = f"spike.{tag}.{TS}@sprintspike-otp.dev"
    body = gen(email)
    uid = body.get("id")
    if uid:
        MADE.append(uid)
    code = str(body.get("email_otp"))
    print(f"\n[{tag}] {email}\n     token=email_otp {code!r} (len {len(code)}) "
          f"verification_type={body.get('verification_type')!r} uid={uid}")
    try:
        r = anon.auth.verify_otp({"email": email, "token": code, "type": literal})
        print(f"     type={literal!r:14s} -> ✓ SUCCESS uid={r.user.id} "
              f"session={'yes' if r.session else 'no'} "
              f"confirmed_at={getattr(r.user, 'email_confirmed_at', None)}")
        return True
    except AuthApiError as e:
        print(f"     type={literal!r:14s} -> ✗ code={getattr(e,'code','')} "
              f"status={e.status} msg={e.message!r}")
        return False


try:
    # The spec's production literal, then the two plausible alternatives.
    ok_email = try_literal("A", "email")
    try_literal("B", "magiclink")
    try_literal("C", "signup")

    print("\n=== VERDICT ===")
    print('type="email" verifies:', ok_email,
          "=> §5.2 call shape is correct" if ok_email else "=> SPEC IS WRONG, stop")

    # What a real signup-token looks like (needs a password per GoTrue).
    EMAIL_S = f"spike.signup.{TS}@sprintspike-otp.dev"
    bs = svc.auth.admin._request("POST", "admin/generate_link", body={
        "type": "signup", "email": EMAIL_S, "password": "Spike-T1-tmp-9x7Q",
        "data": None}).json()
    if bs.get("id"):
        MADE.append(bs["id"])
    print("\n=== generate_link(type='signup') body ===")
    print("     email_otp:", repr(bs.get("email_otp")),
          "verification_type:", repr(bs.get("verification_type")),
          "action_link:", str(bs.get("action_link"))[:100])
finally:
    print("\n=== CLEANUP ===")
    for uid in MADE:
        try:
            svc.auth.admin.delete_user(uid)
            print("deleted", uid)
        except Exception as e:
            print("DELETE FAILED", uid, type(e).__name__, str(e)[:120])
