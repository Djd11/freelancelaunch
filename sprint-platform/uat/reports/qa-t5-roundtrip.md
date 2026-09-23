# QA t5 — LIVE localhost OTP round-trip via admin generate_link (no email)

Run by: qa · 2026-09-16 14:02 · revision `6447d58` · script `uat/scripts/qa_t5_roundtrip.py`
Evidence: `uat/evidence/t5-1789547565.json` (primary), `uat/evidence/t5-replay-probe.txt` (copy re-check),
server log `uat/evidence/t5-server.log`.

## Scope + method
Captain-assigned slice (t5), NOT the gated full-UAT window. Real transport everywhere: the actual
`create_app()` server on **127.0.0.1:5000** (Werkzeug, no reloader), driven over HTTP with cookie-jar
clients; **live dev Supabase** from `.env`; codes minted exclusively via admin `generate_link`
(`properties.email_otp`) — **`POST /auth/otp/send` never called → 0 SMTP slots spent**. All user
creation went through the ledger-capped harness helpers (`mint_user` / `_admin_link`); nothing deleted.

## Verdict — the round-trip works end-to-end; **6/8 raw JSON passes + 2 replay claims re-verified PASS by the 0-cost probe ⇒ all 8 claims hold**
(The raw JSON records the 2 replay assertions as FAIL due to a probe-side substring/HTML-escaping bug; the probe below re-ran those exact claims cleanly. The script has since been fixed with `html.unescape`.)
| # | claim | result | evidence |
|---|---|---|---|
| 1 | signup-family 8-digit code minted for first-ever address | PASS | `code_len=8` `created_by_this_call=True` |
| 2 | **pinned literal `type="email"` redeems signup-family code** over real HTTP → 302 `/sprints`, followed page is NOT the login surface | PASS | `verify=302 -> '/sprints' follow=200 sprints_is_login=False` |
| 3 | `_complete_auth` provisioned exactly one `user_profiles` row (new account) | PASS | `rows=1 display=['uat-otp-p0']` |
| 4 | replay of the redeemed signup code → **no session** | PASS | run-1 `status=200` (success would be 302→/sprints); copy proven in probe |
| 5 | magiclink-family code minted for existing confirmed address, no new user | PASS | `created_by_this_call=False` ledger unchanged by mint |
| 6 | **same literal redeems magiclink-family code** over real HTTP → session | PASS | `verify=302 -> '/sprints' follow=200` |
| 7 | no duplicate provisioning for the existing account | PASS | `rows=1` |
| 8 | replay rejected with the generic copy and session-denied | PASS | probe: replay→200 with flash "That code didn't work — request a new one."; replay-client `GET /sprints` → 302 `/auth/login` |

The two `flash_ok=False` FAILs in the primary evidence JSON are a **probe bug, not a product bug**:
Jinja HTML-escapes the apostrophe (`didn&#39;t`), so my raw-substring match missed; status 200 (not 302)
in both replay responses already proved no session was granted. The dedicated 0-cost probe confirmed the
exact copy and session denial; the script's check was fixed (html.unescape) for future full-window use.

## Matrix meaning (design §4 / T5-addendum, now proven at the ROUTE over HTTP, not just the client)
`type="email"` covers **both account states**: first-ever (signup-family token, account springs into
existence) and existing (magiclink-family token). This is exactly the P0 claim the original driver
step-1 was written to prove.

## Budget + hygiene after this run
- ledger users: **3/8** → `uat-otp-a5@example.com` (pre-existing residue), `uat-otp-p0@sprintspike-otp.dev`, `uat-otp-p0legacy@sprintspike-otp.dev`
- SMTP live sends spent by t5: **0/2** (both still reserved for A2)
- port 5000: released (`pgrep port=5000` → none); server log kept as evidence
- **purge list for the user (post-launch)**: the three addresses above (no deletes performed)
- names deliberately match the planned P0 identities so the later full window reuses them at zero extra cost

## ⚠️ ESCALATION — `uat/scripts/run_t7_uat.py` is corrupted (blocks anyone trusting it)
File is **188 MB / ~3.1 M lines**, timestamped 12:51 today: the real step-1 function (~48 lines) followed
by thousands of repeated partial copies of itself (`"def step1...`, `Tdef step1...`, `7def step1...`).
Not git-tracked (uat/ is untracked by policy). The STATUS entries claiming "11-step driver, 74 assertions,
self-tested" cannot refer to this artifact; the driver needs a rebuild before the gated full window.
I did not touch or delete it. My t5 evidence above is independent of it (fresh script + harness intact).
