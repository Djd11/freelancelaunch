#!/usr/bin/env python
"""qa t5 — LIVE localhost OTP round-trip via admin generate_link (no email sent).

Scoped slice of the OTP/social UAT, run on the captain's explicit assignment (t5),
NOT the gated full window. Zero SMTP: codes come from the admin `generate_link`
API (`properties.email_otp`), never from `POST /auth/otp/send` — the live-send
budget is untouched. Transports are REAL: a live Werkzeug server on
127.0.0.1:5000 hit over HTTP with a cookie jar (no fake seam anywhere in this run);
the Supabase project is the live dev project from .env.

Claims proven (mirrors the original driver's P0 step, whose file was found
corrupted to 188 MB of repeated text — see uat/reports/qa-t5-roundtrip.md):
  1. the pinned verify literal `type="email"` redeems a signup-family  code for a
     first-ever address (account gets created + provisioned);
  2. the same literal redeems a magiclink-family code for an existing,
     already-confirmed address (no duplicate provisioning);
  3. redemption over real HTTP yields a normal session (/sprints 200, not a
     redirect to login);
  4. codes are single-use *at the product edge*: replaying the same code on a
     fresh client is rejected with the generic copy and no session.

Captain constraints honored: uat-otp-*@sprintspike-otp.dev only; every minted
address goes through otp_uat_harness ledger (8-cap, create-only); NO deletes;
SMTP slots NOT fired; identity names match the planned P0 set so the later full
window reuses rather than double-mints.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import otp_uat_harness as H  # noqa: E402  (ledger-capped live helpers)
import httpx  # noqa: E402

BASE = "http://127.0.0.1:5000"
DOMAIN = H.UAT_ADDRESS_DOMAINS[0]          # sanctioned default: sprintspike-otp.dev
FRESH = f"uat-otp-p0@{DOMAIN}"             # first-ever address  (signup-family code)
LEGACY = f"uat-otp-p0legacy@{DOMAIN}"      # existing/confirmed  (magiclink-family code)
EVID_DIR = REPO / "uat" / "evidence"
EVID_DIR.mkdir(parents=True, exist_ok=True)

results: list[dict] = []


def rec(name, claim, ok, evidence):
    results.append({"claim": claim, "id": name, "transport": "LIVE-HTTP",
                    "ok": bool(ok), "evidence": evidence})
    print(f"  [{'PASS' if ok else 'FAIL'}] {claim}\n         {evidence}")


def server_up(timeout=25.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"{BASE}/auth/login", timeout=2).status_code == 200:
                return True
        except Exception:
            time.sleep(0.5)
    return False


def http_csrf(client: httpx.Client) -> str:
    """Browser-identical: scrape the form token from the live login page (same jar)."""
    html = client.get("/auth/login").text
    m = (re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
         or re.search(r'value="([^"]+)"[^>]*name="csrf_token"', html))
    if not m:
        raise RuntimeError("no csrf token on live /auth/login — surface changed?")
    return m.group(1)


def is_login_page(html: str) -> bool:
    return "Choose your sprint" not in html and "/auth/otp/verify" in html


def main() -> int:
    # ---- pre-flight: headroom BEFORE any write (create-only; nothing is deleted) ----
    led = H._ledger()
    print(f"ledger users ({len(led['users'])}/{H.MAX_TEST_USERS}): {led['users']}")
    print(f"ledger live sends in-window: {len(led['sends'])}/{H.MAX_LIVE_SENDS_PER_HOUR} "
          f"(this run must add ZERO)")
    for e in (FRESH, LEGACY):
        H.assert_uat_email(e)
    if H.user_id(LEGACY) is None:
        print(f"minting legacy (existing-account fixture): {LEGACY}")
        H.mint_user(LEGACY)              # admin signup, no email; ledger-charged

    # ---- start the REAL localhost server (no fakes, no reloader) ----
    logf = EVID_DIR / "t5-server.log"
    proc = subprocess.Popen(
        [str(REPO / ".venv/bin/python"), "-c",
         "from app import create_app; create_app().run(host='127.0.0.1', port=5000)"],
        cwd=REPO, stdout=logf.open("w"), stderr=subprocess.STDOUT)
    try:
        if not server_up():
            print("SERVER FAILED TO BOOT; see", logf)
            return 2
        print(f"live server up on {BASE} (pid {proc.pid})")

        for email, link_type, label in [(FRESH, "signup", "first-ever address"),
                                        (LEGACY, "magiclink", "existing confirmed address")]:
            print(f"\n== {label}: {email} ({link_type}-family code) ==")
            tok = H._admin_link(email, link_type)   # fresh single-use code, 0 SMTP
            code = tok.get("email_otp") or ""
            rec("P0.code-shape",
                f"{link_type}-family mint returned a plausible {label} code",
                bool(re.fullmatch(r"[0-9]{8}", code)) if os.getenv("OTP_CODE_LENGTH", "8") == "8"
                else bool(code),
                f"code_len={len(code)} minted={tok['id']} "
                f"created_by_this_call={tok['created_by_this_call']} "
                f"confirmed_at={tok['email_confirmed_at']}")

            c = httpx.Client(base_url=BASE, follow_redirects=False, timeout=10)
            csrf = http_csrf(c)
            r = c.post("/auth/otp/verify",
                       data={"email": email, "token": code, "csrf_token": csrf})
            loc = r.headers.get("location", "")
            r2 = c.get(loc or "/sprints")
            html2 = r2.text
            rec("P0.roundtrip",
                f"POST /auth/otp/verify redeems via real HTTP and yields a session for {label}",
                r.status_code == 302 and "/sprints" in loc and r2.status_code == 200
                and not is_login_page(html2),
                f"verify={r.status_code} -> {loc!r} follow={r2.status_code} "
                f"sprints_is_login={is_login_page(html2)}")
            rows = H.profile_rows(email)
            rec("P0.provision",
                f"exactly one user_profiles row for {label}",
                len(rows) == 1,
                f"rows={len(rows)} display={[x.get('display_name') for x in rows]}")
            c.close()

            # single-use at the product edge: replay from a fresh cookie jar
            c2 = httpx.Client(base_url=BASE, follow_redirects=False, timeout=10)
            csrf2 = http_csrf(c2)
            r3 = c2.post("/auth/otp/verify",
                         data={"email": email, "token": code, "csrf_token": csrf2})
            body = r3.text
            import html as _html
            body_un = _html.unescape(body)  # Jinja escapes the apostrophe: didn&#39;t
            rec("P0.replay",
                f"replayed {link_type} code rejected with generic copy, no session ({label})",
                r3.status_code == 200 and "That code didn't work" in body_un
                and "/sprints" not in r3.headers.get("location", ""),
                f"status={r3.status_code} location={r3.headers.get('location', '')!r} "
                f"generic_copy={'That code didn' + chr(39) + 't work' in body_un}")
            c2.close()
        return 0 if all(x["ok"] for x in results) else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        still = subprocess.run(["pgrep", "-f", "port=5000"],
                               capture_output=True, text=True).stdout.split()
        print(f"\nserver stopped; port-5000 processes left: {still or 'none'}")
        out = {
            "task": "t5 qa live-localhost OTP round-trip",
            "revision": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                        capture_output=True, text=True).stdout.strip(),
            "when": H.stamp(),
            "smtp_slots_spent_by_this_run": 0,
            "addresses_for_purge_list": H._ledger()["users"],  # authoritative, post-run
            "ledger_after": H._ledger()["users"],
            "results": results,
        }
        p = EVID_DIR / f"t5-{int(time.time())}.json"
        p.write_text(json.dumps(out, indent=2))
        print("evidence ->", p)
        npass = sum(1 for x in results if x["ok"])
        print(f"VERDICT: {npass}/{len(results)} assertions passed")


if __name__ == "__main__":
    sys.exit(main())
