# UAT PLAN — Passwordless Email OTP + Google/Facebook OAuth (Supabase)

Owner: **uat-validator** · Spec: `docs/superpowers/specs/2026-09-15-passwordless-otp-social-login-design.md`
Branch: `feature/passwordless-otp-social-login` · Verdict file: `uat/reports/otp-social-login.md` (+ `uat/FINAL_VERDICT_OTP.md`)
Follows house conventions in `uat/BRIEF.md`: evidence-first (HTTP status / screenshot path for every claim), bug format
page + element + expected vs actual + steps + severity, `STATUS.md` line per step.

## 0a. Binding constraints (captain, 2026-09-15 18:09) — these override anything below that conflicts

* **NO EARLY START.** Single authoritative validation window, gated on **t6**. Routes/templates churn through t4/t5,
  so evidence from an intermediate build is worthless. Hold execution; prep only.
* **Live writes:** test auth users only under `uat-otp-*@example.com`, **hard cap 8** for the whole run, every
  address listed in the report for the user's post-launch purge. No deletes.
* **SMTP budget:** the dev project's built-in SMTP is ~2 emails/hour, so **every live `POST /auth/otp/send` costs a
  slot**. Live sends are limited to exactly what A2's enumeration comparison needs (**2 total, same hour**).
  Everything else runs on **in-process fakes**. Enforced mechanically by
  `uat/scripts/otp_uat_harness.py` + ledger `uat/reports/otp_live_budget.json` (refuses a 3rd send in-window, refuses
  a 9th user, refuses any non-`uat-otp-*@example.com` write).
* **`OAUTH_PROVIDERS` shipped value = `google,facebook`** — test that as the default state, plus one pass with
  `OAUTH_PROVIDERS=google` to prove the config plumbing (button visibility is *our* code, provider availability is the
  dashboard's).
* **Dashboard (§6) is user-owned and deferred** → G1 (real mail delivery) and G2 (live Google/Facebook round-trip)
  stay named gaps; A9 = failure paths + PKCE/state/`redirect_uri` assertions on the 302 only.
* **Coverage:** A2 (enumeration) and A6 (collision → no session) are **mine as primary evidence** at HTTP/browser
  level — security-reviewer t4 is static review, qa-eng t3 is unit-level. P2/P3 = a **pytest run only**, no behave
  re-writes.
* **Commit policy:** only the **final UAT report** gets committed; `uat/` prep files stay untracked.

### Method risk the captain flagged — and my pre-flight (do this FIRST, before any area)

`generate_link(type="magiclink")` mints a code whose stored verification type is **magiclink**, while our route is
spec'd to call `verify_otp(type="email")`. Static check of the installed client:
`EmailOtpType = Literal["signup","invite","magiclink","recovery","email_change","email"]`
(`.venv/.../supabase_auth/types.py:48`) and it is a **TypedDict — no runtime validation**, so the literal is handed
straight to GoTrue and only the server decides. That is precisely the un-finished spike item in spec §9.

**Pre-flight P0 (one throwaway `uat-otp-p0@example.com`, 0 SMTP slots):** `otp_for(email)` → `POST /auth/otp/verify`
through the real app route → assert 302 + session UUID == `auth.users.id`.
If it does **not** verify: stop, escalate to the captain with GoTrue's exact error payload, and do **not** substitute
another code path into A2/A4 evidence. Candidate fixes for him to route to backend-eng: (a) route passes
`type="magiclink"`, (b) route accepts the `token_hash` variant (`VerifyTokenHashParams`, already in the spec appendix),
(c) dashboard custom SMTP so a real inbox can be read — needs the user. Note that a failure here is arguably a **real
defect** (the shipped verify path could reject codes GoTrue actually sends for the `{{ .Token }}` template), not just
a harness problem, so I will report it as a Blocker unless proven otherwise.

### Live-send schedule inside the window (fits 2/hour without queueing)

| slot | what | cost |
|---|---|---|
| hour H, slot 1 | A2 new-email send (`uat-otp-a2new@example.com`) | 1 live send |
| hour H, slot 2 | A2 existing-email send (`uat-otp-a2exist@example.com`, pre-minted by `generate_link` so it costs no user slot beyond the cap) | 1 live send |
| hour H+1 | **reserved, unspent** — the captain authorized exactly 2 live sends, so A6's admin-address case is proven under fake transport only and labelled as such (harness refuses a 3rd send / any non-`uat-otp-*` address by design) | 0 |
| reserved | P0 re-run if a code path has to be fixed mid-window | 0 (generate_link sends no mail) |

A3 cooldown piggybacks on A2 slot 1 (the refused resend never reaches GoTrue, so it is free). A4's happy path uses
`otp_for()` → 0 slots. If a live send is refused by GoTrue's own rate limiter mid-run, I record it as an A2 observation
(not a code FAIL) and mark the affected sub-claim `not verified — SMTP budget`, per the captain's no-substitution rule.

## 0. Preconditions (must be true before I start — otherwise I report a blocker, not a FAIL)

| # | Precondition | How I check |
|---|---|---|
| **P0** | **generate_link → `email_otp` → the app's own `/auth/otp/verify` really authenticates** (see Method risk above). Zero cost, do it before anything else | `uat/scripts/otp_uat_harness.py:otp_for()` + one POST |
| P1 | Code is committed on the branch: `otp_send`, `otp_verify`, `oauth_start`, `oauth_callback`, `_complete_auth`, `get_auth_supabase`, `FlaskSessionStorage` | `grep -n "def \|route(" routes/auth.py`, `git log --oneline -5` |
| P2 | Unit tests exist and pass (qa-eng owns this — I only re-run, I don't write them) | `.venv/bin/python -m pytest tests/ -q -k "otp or oauth or auth"` |
| P3 | Existing behave suite is green vs its f3face8 baseline | `behave tests/features/auth-hardening.feature tests/features/landing.feature` |
| P4 | A local instance can boot against the live Supabase project | **verified at baseline:** `flask --app run:app run -p 5000` → `/auth/login` 200, `/` 200; then stopped and port 5000 released so backend/qa runs aren't blocked |
| P5 | Captain confirms live-test-user writes + provider state | **answered 18:09 — see §0a**: `uat-otp-*@example.com` only, cap 8, shipped `OAUTH_PROVIDERS=google,facebook` plus a `google`-only pass |

## 1. Test method — how I get an OTP without a mailbox

Real delivery depends on dashboard SMTP (§6 of the spec, a **user** action, not code). To keep UAT independent of
that, the code path is exercised against the live GoTrue project using the service-role admin API, which returns the
same OTP that would be emailed:

```
supabase._reset_admin_client? -> auth.admin.generate_link({"type": "magiclink", "email": E})
   -> response.properties.email_otp        # supabase-auth 2.31.0, GenerateLinkProperties.email_otp (verified in venv)
POST /auth/otp/verify {email: E, token: <email_otp>}
```

This validates **our** verify/exchange/session/provisioning path end to end. It does **not** validate that a real
email arrives — recorded as gap G1 (spec §6.4/§6.6). If the user later supplies a monitored test inbox, I re-run
areas A2/A4 over the real channel and mark G1 closed.

Two runners, both used:
* **HTTP/Flask test-client** for exact status codes, `Set-Cookie`, redirects, no-leak comparisons.
* **Playwright + system Chrome** (`channel="chrome"`, DISPLAY=:0, headful) for render + interaction + screenshots of
  every login step → `uat/screenshots/otp-*.png`.

Harness: `uat/scripts/otp_uat_harness.py` (mine, untracked). It ships
* `otp_for()/mint_user()` — live admin minting, **sends no mail**, ledger-capped (8 users, non-`uat-otp-*` writes refused);
* `FakeAuth` — in-process replacement for the PKCE auth client that **records every call's arguments**, so the spec's
  transport claims (`verify_otp(type="email")`, `should_create_user: true`, PKCE `flow_type`, `exchange_code_for_session`
  args) are asserted directly rather than inferred. Only the *outbound* GoTrue call is faked: `get_supabase()` /
  `get_client_supabase()` stay live, so session issuance, `user_profiles` provisioning and every redirect are real
  observations. Anything proven this way is labelled **FAKE-TRANSPORT** in the report — never blended with live evidence.
* `live_otp_send()` — the budget-gated real send (see §0a schedule).

## 1b. Corrections forced by T1's spike doc + the code as it has actually landed
(primary sources: `docs/superpowers/spikes/2026-09-15-t1-pkce-otp-spike.md`, `routes/auth.py`,
`services/supabase_client.py`, `config.py`, and `supabase_auth/_sync/gotrue_client.py:1165-1183`)

These override the wording in A1/A2/A4/A5/A8 wherever they conflict — I would rather correct the plan than
manufacture a false FAIL from a stale expectation.

1. **`@example.com` — the conflict is NARROWER than I first escalated, and I have a live data point.**
   T1 spike §6 measured GoTrue rejecting reserved domains — but that measurement is of the **public
   `sign_in_with_otp`** path. On 2026-09-16 I minted `uat-otp-a5@example.com` through the **admin**
   `generate_link` path and it **succeeded** (`auth.users` id `9c2714bf-aa18-4ab6-a2e9-ee2306560cee`,
   read back with `admin.list_users()`). So the admin API accepts the sanctioned space while the
   signup-capable send does not. Consequence for the schedule: **P0, A4, A5, A6 and A12 can all run in
   the sanctioned `uat-otp-*@example.com` space at zero SMTP cost** (admin mint → verify through the
   app). Only **A2's new-address slot** is affected — `sign_in_with_otp` with `create_user` may return
   `email_address_invalid` for `@example.com`, which is a GoTrue policy, not our code. So:
   (a) run A2 slot 1 in the sanctioned space and if it lands in T5's transport-failure branch, that is
   expected and I report the enumeration pair as **not verified live** (my acceptance guard prevents a
   false PASS); (b) if the captain wants a *real* accepted-vs-existing enumeration pair, that needs
   `--domain sprintspike-otp.dev` approved. The decision is his, but the window is no longer blocked
   on it — most of the suite runs either way.
   **Owned mistake:** that user exists because my `--selftest` write ban was enforced only on the
   fan-out path; an explicit `--only 4 --selftest` ran the live mint anyway while I believed nothing
   was written. 1 of my 8 user slots is consumed and the address is in the purge list; the gate
   (`_no_live_writes`) now blocks all four live-write steps under `--selftest` regardless of how they're
   invoked, verified by firing it deliberately.
2. **`type="email"` is already proven live** (spike §2 row A: SUCCESS with an admin-minted `email_otp`;
   row B: `"magiclink"` → `otp_expired`). So P0's risk is much lower than the captain feared — it is now a
   *formality through our route*, and I withdraw my earlier "fallback (a): pass type=magiclink" suggestion:
   the spike shows the server discriminates, and switching literals on failure would mask a real bug.
   Also learned: **an OTP is single-use**, so any control test needs its own fresh token (spike trap #3) — my
   A4 replay and A5 cases are written that way.
3. **Codes are 8 digits, not 6** (spike §3.1; `Config.OTP_CODE_LENGTH = 8`, and `login.html` binds
   `maxlength="{{ otp_length }}"` from config). Design §6.4's "6-digit code" is stale. A1's real risk is now
   the *browser* check: 8 digits must be typeable and the copy must not say "6-digit".
4. **A8's expected URL was wrong.** The PKCE client 302s to **`https://<project>.supabase.co/auth/v1/authorize`**
   (GoTrue hops to Google afterwards), and the client adds only `provider`, `redirect_to`, `code_challenge`,
   `code_challenge_method` — **no `client_id`, no `state`** (those are GoTrue's to add). Method string is
   lowercase **`s256`**; `plain` means PKCE silently off, and `challenge == verifier` means the same. So A8
   asserts: target host/path, `provider`, `redirect_to` ending in `/auth/oauth/callback`, `code_challenge`
   present, method `s256`, challenge ≠ verifier — and I do **not** fail it for lacking `accounts.google.com`
   or `client_id`, which would have been a false FAIL.
5. **Leak-check strings are now exact** (spike §3.4): `otp_expired` / "Token has expired or is invalid",
   `email_address_invalid` / "Email address … is invalid", `otp_disabled` / "Signups not allowed for otp",
   "invalid flow state, no valid flow state found". A5/A9 grep the rendered HTML for these instead of guessing.
6. **Throttle is keyed per address, not one global timestamp** (`routes/auth.py:_cooldown_left` stores a dict
   `email → epoch`, deliberately, so a typo can't lock the correct address out for 60 s). A3 therefore gains a
   case: after a send to A, a send to B in the same session must reach the transport (2 calls), while a resend
   to A must not (still 1).
7. **`user_profiles` is keyed by the `user_id` column** (`_complete_auth` queries `.eq("user_id", uid)`), and
   provisioning uses `upsert(..., on_conflict="user_id", ignore_duplicates=True)`. My duplicate-row assertion
   must query `user_id` — my first harness draft queried `id`, which returns `[]` and would have *fabricated*
   a "not provisioned" finding. Fixed and commented in place.
8. **Templates were refactored mid-flight** (18:52): the auth markup now lives in `templates/_auth_panel.html`,
   which `login.html` and `signup.html` both render. Any file-scoped grep of `login.html` alone reports a false
   FAIL, so A1 greps the rendered surface (`/auth/login` vs `/auth/signup` expose the same form + buttons) and
   the presence check scans the whole template tree.
9. **OAuth is a 2-request, 1-client-jar flow**: `sign_in_with_oauth` calls `_remove_session()` (l.1171), so the
   jar that starts must be the jar that redeems; and `_get_url_for_provider` clears any previous verifier on a
   second start (spike §1 trap: last-write-wins). A9 starts a *second* `oauth_start` in the same jar to prove
   the first code becomes unusable — that is a real PKCE property worth evidencing, not just a happy-path test.
10. **`get_auth_supabase()` is the seam** (T1 landed it with that name; cached on `g.auth_supabase`,
    registered in `close_request_clients()`), so `make_app()` resolves it and A10 checks that exact attr.
    Also noted: `_new_client(url, key, options)` keeps a lazy `create_client` import precisely so
    `patch("supabase.create_client")` still works — that's qa's seam, not mine; I patch the factory.

**Build-state risk to keep naming:** at 18:57 this tree is `HEAD=b27ba5c` with the OTP implementation present as
*uncommitted* edits (`routes/auth.py`, `templates/*`, `config.py`, `services/supabase_client.py` modified). The
commit the captain referenced (`0e3785a`, in the wiped `/tmp/sp-impl-wt`) is not reachable here. My driver therefore
records a content **fingerprint** (`_fingerprint()` over the five files under test) with every run, and step 0 flags
`--expect-commit` mismatches instead of silently testing the wrong thing. A dirty tree is testable but not
reproducible: the signed report must cite a real t6 SHA.

## 2. Areas

### A1 — Login surface (spec §5.4)
GET `/auth/login` and `/login` (alias). Expect: primary block "Email me a sign-in code"; collapsible
"Use my password instead" posting to the existing `/auth/login` handler; provider buttons **only** for providers in
`OAUTH_PROVIDERS`; code step reachable at `?step=code` with masked email + resend link; CSRF token in every form;
`/auth/signup` renders the same surface in create-account mode with a first-name field, old links intact.
**PASS** all of the above renders with no 500/console error and no layout break at 375 px and 1280 px.
**Blocker** login page 500/blank. **Major** FB button shown while dashboard provider is off; password form removed.

### A2 — OTP send (spec §5.2)
POST `/auth/otp/send` for (a) a brand-new email, (b) an existing email (`demo@sprint-platform.local`),
(c) `admin@sprint-platform.local`, (d) malformed/empty email, (e) missing field.
**Transport per captain's budget (see §0a schedule):** (a) and (b) are **live** (the only 2 SMTP slots in hour H;
(b)'s user is pre-minted under `uat-otp-*@example.com` rather than `demo@` so nothing outside the sanctioned address
space is touched). (c), (d), (e) run on **fakes** and are labelled as such — the enumeration claim for (c) still holds
because the response must be byte-identical to (a)/(b), which is exactly what the fake harness asserts.
Expect (a–c): **identical** generic response body + status + timing band, no session cookie, `otp_last_sent_at` set.
Expect (d/e): field-validation message, no GoTrue call.
Extra assertion: **no user enumeration** — compare (a) vs (b) vs (c) bodies byte-for-byte; a "user exists" difference = **Major**.

### A3 — Resend cooldown (spec §5.2)
Second send immediately after a successful one → refused with countdown shown; server-side is authoritative
(replay the POST with curl, cookies kept, at t+5 s and t+61 s; must refuse then accept). Cooldown state must not
leak across browsers/sessions (fresh cookie jar can send immediately). **Blocker** if cooldown is client-only.

### A4 — OTP verify happy path
`generate_link` → POST `/auth/otp/verify` with the 6-digit code. Expect 302 → `/sprints`, session cookie set,
`session["user_id"]` equals the real `auth.users.id` UUID for that email, exactly **one** `user_profiles` row created
(`display_name` = name hint / email prefix, `is_public` false), welcome flash, `/sprints` renders 200 for them.
Re-run verify with the same code (replay) → must fail cleanly, not re-auth. Second `_complete_auth` for the same uid
must not duplicate the profile row (spec §4 "provisions once").

### A5 — OTP verify failure paths
Wrong 6-digit code; code for a different email; expired/absent code; empty token; 4–5 digit token; oversized token;
SQL/xss-ish string in the email field. Expect 200 re-render with a **generic** error, **no session cookie**, no 500,
no stack trace, no GoTrue error code echoed (e.g. `email_not_confirmed`, `token_expired` shown verbatim = **Major**
info leak). Then verify the happy path still works afterwards (no lockout corruption).

### A6 — Signup-collision takeover regression (the headline security fix)
The old bug: `POST /auth/signup` with an **existing** email auto-logged the caller in (spec §2, §5.2).
Test: with `admin@sprint-platform.local` and with a verified demo user's email — no session cookie after the POST;
`GET /sprints` and `GET /admin` still redirect to login; the response is the same generic "code sent" shape as A2.
**Transport:** primary evidence on **fakes** (real user_profiles/auth.users rows stay live, so the "no session" claim is
a genuine HTTP observation — the fake only replaces the *outbound* GoTrue call). The captain authorized only 2 live
sends (both spent on A2), so the admin-address case is proven **fake-transport + live response-shape comparison
against A2's two slots**, and labelled that way. The essential assertion is unchanged either way: a POST to the signup
funnel for an address that already exists must **never** set `session["user_id"]`.
Repeat via the browser as a logged-out visitor and confirm no privileged landing. **Blocker** if any session is set.
Also: legacy email-only account (random unknown password) can now get in via OTP and still cannot via a guessed
password — proves the "stranded accounts" claim (spec §8) without data migration.
**Note on (b):** I will not send a live OTP to `demo@`/`admin@` unless the captain explicitly okays mail to those
seeded addresses; the sanctioned `uat-otp-*` space covers the same assertion.

### A7 — Password path still intact (backwards compat, spec §4)
`POST /auth/login` correct → 302 `/sprints`; wrong → `Invalid email or password.` + no session; `/login` alias 302s.
`auth-hardening.feature` must be 7/7 (baseline at f3face8). Existing sessions issued before the change keep working.

### A8 — OAuth start (spec §4, §5.2)
`GET /auth/oauth/google` → 302 to `accounts.google.com` with `client_id`, `redirect_uri=<base>/auth/oauth/callback`,
`response_type=code`, **`code_challenge` + `code_challenge_method=S256` + `state`**.
**PKCE assertion is by invariant, not by key name** (captain's correction): the exact Flask-session storage key is
whatever T1's `FlaskSessionStorage` chose, so I read it out of the committed code / backend-eng's notes at UAT time and
then assert — (i) after `oauth_start`, the **signed session cookie** contains a verifier where the *same* code's
`FlaskSessionStorage` would put it (decode the cookie and diff against the key the implementation writes), (ii) the
verifier is **absent from every HTML/JS byte** of the response, (iii) it is **bound to the same cookie jar** (a second
client without that cookie cannot complete the callback), and (iv) it is **cleared after callback redemption/replay**.
None of that hardcodes a name, so a rename in t4/t5 can't produce a false PASS or a stale FAIL.
`/auth/oauth/facebook` → same shape to Meta, **or** 404/400 + hidden button when `OAUTH_PROVIDERS=google` — test both
env values (spec §6.3). Provider matrix per captain: **`google,facebook`** is the shipped default state to validate,
plus one pass with `OAUTH_PROVIDERS=google` — the button-hiding plumbing is code we own and must be proven, while
whether Meta is actually enabled is the dashboard's business (G2).
`GET /auth/oauth/evil`, `/twitter`, `..`, `<script>`, empty → rejected (allow-list), no 500,
no open redirect through `redirect_to`. Case variants (`GOOGLE`) behave per the lowercase-set rule.

### A9 — OAuth callback failure paths (no provider account needed)
`/auth/oauth/callback` with no `code`; with `code=invalid`; with a code but a **cleared/mismatched** session
(verifier gone); same code replayed twice. Expect the generic flash "Social sign-in didn't complete — try the email
code." on `/auth/login`, 200, **no session**, no 500, no raw `AuthApiError` text. This is the realistic coverage
ceiling without a Google test account (G2). A **full** Google round-trip is a **release gate** before the button is
enabled in prod (spec §7 residual risk) and needs the user's browser credentials — I will hand that checklist over
rather than fake it.

### A10 — Session contract + teardown (spec §2, §5.1)
Session key stays `user_id`, UUID-validated; `g.user` loads; `require_login` still gates protected routes;
`/auth/logout` clears auth **and** the PKCE verifier residue (same invariant test as A8 — no key name hardcoded); a
request-scoped `get_auth_supabase()` client is closed
(no leaked session across requests — check `close_request_clients()` registered attrs). Also: `persist_session=False`
must not leave tokens in a file/cookie beyond the PKCE pair.

### A11 — Config + deploy surface (spec §5.3)
`OAUTH_PROVIDERS` parsing (empty, weird spacing, uppercase, unknown token like `twitter`), `OTP_EMAIL_ENABLED=false`
→ OTP form hidden/disabled while password+OAuth still work, `PUBLIC_BASE_URL` drives `redirect_to` for both
localhost and prod. `.env.example` documents the two new vars; `render.yaml` untouched (`git diff --stat`); app boots
with **no** new env set (defaults) — important because Render has no such vars yet.

### A12 — Whole-journey regression (nothing else broke)
Real browser: OTP login as a fresh user → picker → start sprint (the one permitted write, twice → idempotent) →
dashboard → day → proposal builder render → mentor render → logout → anon redirect. Plus
`behave tests/features/` full run compared against the recorded f3face8 baseline (21/21 verify suite; known-failing
sets listed in `uat/reports/verify-auth-fix.md`) — any **new** failure = regression, report severity accordingly.

## 3. Severity / exit criteria

* **Blocker** — any privilege escalation (A6), login 500, OTP happy path unable to produce a working session,
  PKCE/state absent on OAuth start, session set without verification.
* **Major** — user enumeration, GoTrue error leakage, client-only cooldown, button shown for an unconfigured
  provider, duplicate `user_profiles`, any new behave failure vs baseline.
* **Minor** — copy/layout/a11y/countdown polish.
* **UAT PASS** = P1–P5 met, A1–A12 executed with evidence, zero open Blocker/Major, and every uncovered item listed
  under Gaps with an owner. Report per area + `STATUS.md` line each step; bug format from `uat/BRIEF.md`.

## 4. Gaps I will state honestly (not silently skip)

* **G1 — real email delivery** (Brevo/Resend SMTP + `{{ .Token }}` template, spec §6.4/§6.6): dashboard-only, needs the
  user. OTP is verified via admin `generate_link`, so the app path is covered but delivery is not.
* **G2 — live Google/Facebook round-trip**: needs a Google test account the user controls, and Meta app review for FB
  (spec §6.3). Failure paths are covered (A9); success path is a pre-enable gate, handed to the user as a checklist.
* **G3 — SMS/phone OTP, Apple, X/LinkedIn**: explicitly out of scope (spec §1).
* **G4 — prod Render deploy verification**: I test localhost + committed code; the same matrix on
  `https://freelancelaunch.onrender.com` is one short pass I can repeat after deploy if the captain wants it.
* **G5 — session cookie absolute expiry**: pre-existing accepted risk (spec §7), not a new bug.
* **G6 — behave full-suite regression is expensive, so it is opt-in.** Baseline numbers I verified myself, from
  `uat/reports/behave-full-run1.log`: **210 scenarios** (independently counted across `tests/features/*.feature`) =
  145 passed / **58 failed** / 7 error, 15 of 20 features red, **30 min 38 s** wall. P3 therefore runs *targeted* files
  (`auth-hardening`, `landing`, `api` + any new auth specs) — cheap and decisive. A full-suite diff vs the 58-fail
  baseline is an **optional** A12 add-on the captain must authorize: 30+ min, and it must not overlap qa-eng's t6 gate
  nor my browser run (behave executes the app in-process against the same live project and rewrites the same seeded
  users).
* **G7 — behave writes to the same live project and cleans up *tracked* rows.** Verified in source, not assumed:
  `tests/environment.py::before_scenario` → `reset_live_adapter()`, and
  `tests/live_db_adapter.py::cleanup_scenario` deletes the scenario's tracked rows in FK-safe order
  (`sprints` by created-or-reused id, plus `user_profiles` for the fixture users seeded at l.106/141/171 —
  `demo@`, `uat@test.local`, `mentor@test.local`, `admin@` — and cascades their sprint children). Two consequences:
  (i) my "provisioned **exactly once**, correct `display_name`" assertion is safe on a `uat-otp-*` identity — behave
  never tracks or deletes those rows — but **untrustworthy on `demo@`/`admin@`**, whose profile rows come and go per
  scenario, so I use fixture users for status/redirect assertions only; (ii) behave does **not** clean up my
  `uat-otp-*` rows at all, which is precisely why the report must carry the exact purge list.
  Timing: never run behave concurrently with my browser pass (same project, same fixture identities).
  (Corrected from my first draft, which overstated this as "deletes all sprints for the seeded users".)
* **G8 — no browser-level Google/Facebook button click-through** beyond the 302 assertions (G2's consequence):
  recorded as "button renders + initiates a correct PKCE request", not "a user completed a Google login".

## 6. Execution driver (written, self-tested, NOT fired)

`uat/scripts/run_t7_uat.py` — 11 steps, one process per step so no fake/patch leaks between steps
(`--inline` overrides), ordered by SMTP cost: 0 P1 gate → 1 P0 → 2 A2 (the only 2 slots) → 3 A4 →
4 A5 (+4b arg-shape) → 5 A3 → 6 A6 → 7 A8/A9/A9b → 8 A11 → 9 behave → 10 browser (`--browser`, off
until the t6 go). `--report` renders the committed report skeleton *from* the evidence JSON, and a
`--selftest` run can only ever write
`uat/reports/otp-social-login.SELFTEST-preview.md` (banner: NOT UAT EVIDENCE).

Self-test status on `0c7171e`: **70 assertions, 0 fail, 3 named gaps** (25 LIVE / 23 FAKE-TRANSPORT /
22 STATIC), 1 m 44 s. Steps 1–4 (live writes) and 9/10 stay unfired by `--selftest` design.

**Three things the code review forced into the script (each would have been a false result):**
1. **A2 now asserts acceptance *before* equality.** T5's deliberate deviation shows
   "We couldn't send a code just now" on a genuine transport failure — so if both live sends fail
   (rejected address space, SMTP/429), the two bodies are byte-identical and my enumeration claim
   would "PASS" having proved nothing. `_send_accepted()` gates every A2 equality check and the claim
   is withheld (not fudged) otherwise.
2. **A8 runs on the REAL auth client and is class LIVE at zero SMTP cost** — `sign_in_with_oauth`
   performs no network call (`gotrue_client.py:1165-1183` builds `/authorize` locally, and
   `code_verifier=""` makes `exchange_code_for_session` read the verifier from `FlaskSessionStorage`,
   per T2's own note). Faking it would have had me asserting against my own fake. New live checks
   this unlocked: `Set-Cookie` present on `oauth_start` (T1's `session.modified` trap — if it regresses
   the callback dies with "invalid flow state"), and verifier **rotation** on a second start in the same jar.
3. **A5 split into two halves, because T5 added `_token_is_plausible()` before GoTrue.** The HTTP half
   stays LIVE (a wrong code never sends mail): every junk tier → 200 + no session + no
   `otp_expired`/`Token has expired` leak. The argument half is inherently FAKE-TRANSPORT (only a
   recording fake can see what we hand GoTrue): `07368987`/`45480348`/`00000000` must reach the
   transport **verbatim, str-typed, `type="email"`** — any `int()` on the path truncates a leading-zero
   code to 7 digits and silently locks real users out — while 7-digit, 9-digit, `abcdefgh`,
   `²0245678`, `١٢٣٤٥٦٧٨`, `"07368 987"`, `0abc-def`, `1` must **never** reach it.
   The Unicode tiers are why `[0-9]` beats `\d`: `\d` matches `²` and Arabic-Indic digits.

Also de-theatred: "verifier cleared after redemption" is *not* asserted against the fake (clearing is
the library's `remove_item`, which my fake never runs). What is asserted instead: our route's exchange
argument shape, and that a replayed code with a cleared bucket yields the generic recovery copy and no
session. §8.1's six clearing sites are security-reviewer's behavioural finding (t10 CHECK 2) and my
report cites it as STATIC rather than re-proving it with a fake.

## 5. Hard rules (create-only is now a team rule, and it binds me hardest)

No destructive actions. No purge scripts, no deletes, no admin data changes, no `auth.users` deletions; the only
writes are normal UI actions (start sprint) and creating clearly-prefixed `uat-otp-*@<approved-domain>` test users.

**Why this is executed, not just written:** backend-eng's spike cleanup used an over-broad filter and deleted two
stale husk accounts it had not created (`11c3e099-…` `uat.user.1788795034@example.com`, `cdb275ae-…`
`live_qa_1788762183@example.com`; app-data impact verified zero — seeds `admin@`/`demo@`/`other@` intact). The
captain has made **create-only + full purge list + zero deletes** a hard team rule. I hold a service-role key and
could quietly "tidy up" between runs, so step 0 of the driver now runs `audit_myself()`, which *parses my own
source with `ast`* and fails the run if any `delete`/`delete_user`/`drop`/`truncate`/`purge` **call** exists
(prose in a docstring can't false-flag it), asserts there is no *live dependency* on the two deleted UUIDs/emails
anywhere in `tests/` or `templates/`, and prints the user-cap headroom before a single write happens.

**Consequences for the run, adopted as instructed:**
* Every identity is created fresh at UAT time under `uat-otp-*` and listed in the report's purge list — including
  the one my own bad `--selftest` gate already minted (`uat-otp-a5@example.com`,
  `9c2714bf-aa18-4ab6-a2e9-ee2306560cee`), which is now a named entry rather than a forgotten side effect.
* **Cap math:** `uat-otp-p0`, `-a2new`, `-a2exist`, `-a4`, `-a6` still to mint **+** the spent `-a5`
  = **6 of 8**, leaving 2 for a re-run after a mid-window fix. If a fix forces a second P0/A4 pass I do not
  silently exceed the cap — I stop and ask.
* **Baseline provenance:** my A12 reference is `uat/reports/behave-full-run1.log` (210 scenarios / 58 fail /
  30 m 38 s), recorded on the seed set — which the audit confirms never referenced the husks — so the deleted
  accounts do **not** invalidate the baseline. No UUIDs are baked into my fixtures, so nothing needs regenerating
  beyond creating fresh `uat-otp-*` identities at run time, which was already the plan.
* **Zero deletes** even for my own mess: the husk incident is exactly why I won't "clean up" my 6 test users at the
  end, and the report hands the list to the user instead.

Machine-enforced, again so a rushed run can't violate them: `uat/scripts/otp_uat_harness.py` refuses any live write
outside the sanctioned prefix/domain, caps test users at **8**, caps live OTP sends at **2/hour** via the ledger
`uat/reports/otp_live_budget.json`, and hard-refuses all four live-write steps under `--selftest` on every
invocation path (added after I breached my own write-free claim). Report discipline: every claim carries `LIVE`,
`FAKE-TRANSPORT` or `STATIC`, and the final **report only** is committed (`uat/` prep stays untracked).
