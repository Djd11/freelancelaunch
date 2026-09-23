"""GoTrue email-OTP `type` matching matrix (t4 pre-work, authorized by captain).

The bogus-token probe (spike_pkce_storage_and_otp_types.py, part C) could not
discriminate `type` literals: every string returned the byte-identical
`403 otp_expired`, because token lookup precedes type validation. This script maps
the question with a GENUINELY ISSUED token:

  mint (admin/generate_link — sends NO email, burns NO SMTP quota)
      -> verify (raw POST /auth/v1/verify with the real `email_otp` code; 8 digits
         on this project, and ~1 in 10 begin with a leading zero, so it must stay
         a string end to end — see docs/compare/spike_answers.md "Measured OTP codes")

across type literals, for two different token families (magiclink-issued and
signup-issued). Each cell mints its own fresh token immediately before verifying,
because GoTrue stores one pending email token per user and a successful verify
consumes it.

Lifecycle: creates throwaway auth.users, deletes them in a finally block. It
touches ONLY auth.users rows for synthetic @example.com addresses — no
user_profiles rows, no sprint data, no dashboard settings.

NOT a substitute for the app-path round-trip: /otp-minted tokens for an existing
user come through the same magiclink family, but the real user flow also depends
on the dashboard "Magic link" template carrying `{{ .Token }}` (spec §6.4). This
maps server-side type matching only.

Run: .venv/bin/python docs/security/spike_gotrue_type_matrix.py
"""
import json
import os
import time
import urllib.error
import urllib.request
import uuid

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

BASE = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
ANON = (os.getenv("SUPABASE_ANON_KEY") or "").strip()
SERVICE = (os.getenv("SUPABASE_SERVICE_ROLE_KEY")
           or os.getenv("SUPABASE_SERVICE_KEY") or "").strip()

TAG = time.strftime("%m%d%H%M%S", time.gmtime())
STAMP = uuid.uuid4().hex[:6]

LITERALS = ["email", "magiclink", "signup", "recovery", "bogus"]


def raw_verify(email, token, type_literal):
    """POST /auth/v1/verify exactly as the app would. Returns (status, body-dict)."""
    url = BASE + "/auth/v1/verify"
    body = {"email": email, "token": token, "type": type_literal}
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "apikey": ANON,
            "Authorization": f"Bearer {ANON}",
            "Content-Type": "application/json",
            "X-Client-Info": "supabase-py/security-spike",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw or "{}")
        except json.JSONDecodeError:
            return e.code, {"raw": raw[:200]}
    except Exception as exc:  # noqa: BLE001
        return -1, {"error": f"{type(exc).__name__}: {exc}"}


def summarize(status, body):
    """Collapse a verify response into a matrix cell verdict."""
    if status == 200 and body.get("access_token"):
        user = body.get("user") or {}
        return "ACCEPTED", f"session issued (uid={str(user.get('id'))[:8]}…)"
    code = body.get("error_code") or body.get("msg") or body.get("error") or "?"
    return f"HTTP {status}", str(code)[:60]


def run_matrix(sb, family, mint_for, probe_email, per_cell_email=False):
    """mint_for(email) -> generate_link kwargs.

    per_cell_email=True is required for the signup family: generate_link(type=
    "signup") PROVISIONS the user, so a second mint on the same address fails with
    "A user with this email address has already been registered" and the rest of the
    row is lost. One address per cell keeps every cell measurable.
    """
    print(f"\n### token family: {family}   (probe email "
          f"{'one fresh address per cell' if per_cell_email else probe_email})")
    print(f"{'verify type':<12} {'verdict':<12} detail")
    print("-" * 78)
    rows = []
    uids = []
    for literal in LITERALS:
        email = (f"{probe_email.rsplit('@', 1)[0]}-{literal}@example.com"
                 if per_cell_email else probe_email)
        try:
            link = sb.auth.admin.generate_link(mint_for(email))
            otp = link.properties.email_otp
            vtype = getattr(link.properties, "verification_type", "?")
            # generate_link returns the user it minted against — this is how we
            # find the signup-family uid (there is no get_usersByEmail in 2.31.0).
            uid = getattr(getattr(link, "user", None), "id", None)
            if uid and uid not in [u for u, _ in uids]:
                uids.append((uid, email))
        except Exception as exc:  # noqa: BLE001
            print(f"{literal:<12} {'MINT-FAIL':<12} {type(exc).__name__}: "
                  f"{str(exc)[:52]}")
            rows.append((family, literal, "MINT-FAIL", str(exc)[:60]))
            continue
        status, body = raw_verify(email, otp, literal)
        verdict, detail = summarize(status, body)
        print(f"{literal:<12} {verdict:<12} minted verification_type={vtype!r}; {detail}")
        rows.append((family, literal, verdict, detail))
        time.sleep(1.5)  # stay clear of issuance rate limiting between mints
    return rows, uids


def main():
    if not (BASE and ANON and SERVICE):
        print("SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY required")
        return 1

    from supabase import create_client

    sb = create_client(BASE, SERVICE)
    created = []
    results = []

    # ---- Cleanup runs even if a phase raises: this script creates live identities.
    try:
        results += probe_families(sb, created)
    finally:
        print("\n### cleanup")
        seen = set()
        for uid, mail in created:
            if uid in seen:
                continue
            seen.add(uid)
            try:
                sb.auth.admin.delete_user(uid)
                print(f"  deleted {mail} uid={uid}")
            except Exception as exc:  # noqa: BLE001
                print(f"  !! DELETE FAILED {mail} uid={uid}: "
                      f"{type(exc).__name__}: {exc}"
                      " — remove manually (Authentication → Users)")

    # ---- Matrix rollup
    print("\n### matrix rollup (ACCEPTED = that literal redeems that token family)")
    print(f"{'family':<46} {'type':<12} {'verdict'}")
    print("-" * 78)
    for family, literal, verdict, _detail in results:
        print(f"{family:<46} {literal:<12} {verdict}")
    return 0


def probe_families(sb, created):
    """Run both token families; append any new uids into `created` for cleanup."""
    results = []

    # ---- Family 1: magiclink token on a PRE-EXISTING, confirmed user.
    # This is exactly the shape an existing account gets from
    # sign_in_with_otp(should_create_user: true) — the case spec §8 relies on.
    email_ml = f"sec-spike-ml-{TAG}-{STAMP}@example.com"
    res = sb.auth.admin.create_user({
        "email": email_ml,
        "password": f"Spike!{STAMP}{uuid.uuid4().hex}",
        "email_confirm": True,
        "data": {"display_name": "security-spike-temp"},
    })
    uid = getattr(res.user, "id", None)
    if uid:
        created.append((uid, email_ml))
    print(f"created throwaway confirmed user: {email_ml} uid={uid}")

    ml_rows, _ml_uids = run_matrix(
        sb, "magiclink (user exists, confirmed)",
        lambda mail: {"type": "magiclink", "email": mail}, email_ml,
    )
    results += ml_rows

    # ---- Family 2: signup token (unconfirmed user path).
    su_password = f"Spike!{STAMP}{uuid.uuid4().hex}"
    # generate_link(type=signup) provisions the user itself in GoTrue, so each cell
    # needs its own address; uids come back on the response for cleanup.
    su_rows, su_uids = run_matrix(
        sb, "signup (minted via generate_link type=signup)",
        lambda mail: {"type": "signup", "email": mail, "password": su_password},
        f"sec-spike-su-{TAG}-{STAMP}",
        per_cell_email=True,
    )
    results += su_rows
    created.extend(su_uids)
    return results


if __name__ == "__main__":
    raise SystemExit(main())
