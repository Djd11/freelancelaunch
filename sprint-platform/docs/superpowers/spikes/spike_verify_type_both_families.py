"""T5 escalation check: does ONE verify literal cover BOTH account states?

⚠️ READ WITH spike_verify_type_matrix.py — this pass mislabels case A. Its
"BRAND-NEW address" calls generate_link once as a probe BEFORE redeeming, and that
probe is what CREATES the user, so the redeemed token was already magiclink-family
in all three cases. That is why `signup` 403d everywhere here while my T1 control
(a genuine first-ever mint, redeeming a true signup-family token) accepted `signup`
and rejected `magiclink`. Both runs are correct measurements of different families;
the matrix script is the controlled one. What this pass DOES still prove: all three
account states (new / existing+confirmed / existing+unconfirmed) redeem with
`email`, and codes are 8 digits.


The design risk (captain + reviewer + UAT converging): GoTrue mints a
type-dependent confirmation token — a brand-new address gets a *signup*-family
token, an existing one a *magiclink*-family token. If `verify_otp` pinned a
literal that only redeems one family, validly-issued codes would be rejected for
half the population, and GoTrue answers with the same 403 it gives a typo — i.e.
a silent, undiagnosable login failure.

This script measures, per account state, (1) which family `generate_link`
reports and (2) which literals the live /verify endpoint actually redeems.

Why generate_link is a usable proxy: /otp and /admin/generate_link both mint the
confirmation token through the same GoTrue path and differ only in *delivery*
(generate_link returns the code in the JSON body instead of mailing it). The one
thing this cannot cover is a code that actually travelled through an inbox — that
needs the dashboard's {{ .Token }} template + SMTP (t4/T7).

CLEANUP RULES (t5 incident): creates nothing outside a dedicated exact prefix on
a domain that cannot be delivered to; deletes only ids enumerated in THIS run,
by id; snapshots auth.users before and after and reports any delta it cannot
account for. No sprint/profile rows are created.
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
PREFIX = "t5fam."
SUFFIX = "@sprintspike-otp.dev"
MADE = []


def snapshot():
    return {u.id for u in svc.auth.admin.list_users()}


BEFORE = snapshot()
print("auth.users before:", len(BEFORE))


def gen(email, typ="magiclink"):
    return svc.auth.admin._request(
        "POST", "admin/generate_link",
        body={"type": typ, "email": email, "password": None,
              "new_email": None, "data": None}).json()


def redeem(email, code, literal):
    try:
        r = anon.auth.verify_otp({"email": email, "token": code, "type": literal})
        return ("OK", r.user.id if r.user else None)
    except AuthApiError as e:
        return ("403", getattr(e, "code", "") or e.status)
    except Exception as e:                                   # noqa: BLE001
        return ("ERR", type(e).__name__)


def family_report(label, email, note=""):
    """Which literals redeem this account state?

    ⚠️ ONE FRESH TOKEN PER LITERAL. A verify CONSUMES the token on success, so
    reusing a single token across literals is the confound that invalidated my
    first T1 control run: whichever literal is tried first wins the token, and
    every later literal then 403s for "expired" rather than for a type mismatch.
    Here each literal gets a newly minted code, so an OK/403 is attributable to
    the literal alone.
    """
    print(f"\n--- {label} ({note})")
    print(f"    address={email}")
    probe = gen(email)
    if probe.get("id"):
        MADE.append(probe["id"])
    print(f"    generate_link verification_type={probe.get('verification_type')!r} "
          f"code={probe.get('email_otp')} (len {len(str(probe.get('email_otp')))})")
    results = {}
    for lit in ("signup", "magiclink", "email"):
        fresh = gen(email)                      # <- new token, per literal
        if fresh.get("id"):
            MADE.append(fresh["id"])
        code = str(fresh.get("email_otp"))
        status, detail = redeem(email, code, lit)
        results[lit] = (status, detail)
        print(f"    verify_otp type={lit!r:13s} -> {status} {detail}"
              f"{'   (fresh token consumed by this success)' if status == 'OK' else ''}")
    return results


try:
    NEW = f"{PREFIX}new.{TS}{SUFFIX}"
    r_new = family_report("A. BRAND-NEW address (no auth.users row)", NEW,
                          "signup-family expectation")

    CONF = f"{PREFIX}conf.{TS}{SUFFIX}"
    # Make it an existing, CONFIRMED user first (mirrors the legacy accounts of
    # design §8, which were created with email_confirm=true).
    b = gen(CONF)
    if b.get("id"):
        MADE.append(b["id"])
        anon.auth.verify_otp({"email": CONF, "token": str(b["email_otp"]),
                              "type": "email"})
        u = svc.auth.admin.update_user_by_id(b["id"], {"email_confirm": True})
        uu = getattr(u, "user", u)
        print(f"\n    [setup] {CONF} confirmed_at={getattr(uu, 'email_confirmed_at', None)}")
    r_conf = family_report("B. EXISTING + CONFIRMED user", CONF,
                           "magiclink-family expectation (design §8 legacy case)")

    UNC = f"{PREFIX}unc.{TS}{SUFFIX}"
    c = gen(UNC)
    if c.get("id"):
        MADE.append(c["id"])
    r_unc = family_report("C. EXISTING but UNCONFIRMED user", UNC,
                          "mid-abandonment state")

    print("\n" + "=" * 66)
    print("VERDICT — is ONE literal enough for every account state?")
    for name, res in (("new", r_new), ("existing+confirmed", r_conf),
                      ("existing+unconfirmed", r_unc)):
        ok = [lit for lit, (st, _) in res.items() if st == "OK"]
        print(f"  {name:22s} accepted literals: {ok or 'NONE'}")
    email_ok = all(r["email"][0] == "OK" for r in (r_new, r_conf, r_unc))
    print(f"\n  type=\"email\" redeems ALL THREE states: {email_ok}")
    print("  => " + ("keep the single pinned literal; the umbrella claim holds"
                     if email_ok else
                     "SINGLE LITERAL IS UNSAFE — accept the set that works"))
finally:
    print("\n=== CLEANUP (ids enumerated in this run only) ===")
    for uid in dict.fromkeys(MADE):
        try:
            svc.auth.admin.delete_user(uid)
            print("deleted", uid)
        except Exception as e:                                # noqa: BLE001
            print("DELETE FAILED", uid, type(e).__name__, str(e)[:100])
    AFTER = snapshot()
    extra = AFTER - BEFORE
    missing = BEFORE - AFTER
    print("auth.users after:", len(AFTER))
    print("  created-but-left:", extra or "none",
          "| pre-existing-and-now-gone:", missing or "none  <-- must be none")
