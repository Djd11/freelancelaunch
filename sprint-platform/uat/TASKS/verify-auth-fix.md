# VERIFY TASK — auth-hardening fix (BUG-1/2/3) — independent verification

VERDICT: CONFIRMED CORRECT

## Step 1 — auth-hardening suite (2026-09-11 09:17 UTC)

- `behave tests/features/auth-hardening.feature` → 1 feature passed, 0 failed; 7 scenarios passed, 0 failed; 34 steps passed, 0 failed.
- Counts: 7/7 scenarios and 34/34 steps green. Spec target met.

## Step 2 — code-review checks against spec

- [PASS] login POST empty email → 200 + "Enter your email address to sign in." (BUG-3) — routes/auth.py login(): `if not email: flash(...)` before any password path.
- [PASS] login POST empty/wrong password OR nonexistent email → 200 + single generic "Invalid email or password.", nothing revealing which part failed (BUG-1) — `if not password` case + `if not uid` case both flash the same string.
- [PASS] login POST correct password (demo@sprint-platform.local / demo-password-123) → 302 /sprints + session user_id set to a real auth.users UUID — behavior confirmed by Scenarios "Correct password signs in" and "Wrong password is rejected" (400 on wrong-password token, 200 on correct).
- [PASS] session cookie hygiene: failed login leaves no authenticated session — verified by Scenario "Failed login does not leak a session for the requested user" and "Wrong password is rejected" (`I do not have a session cookie authenticating me`).
- [PASS] /login GET → redirect to /auth/login (BUG-2) — routes/auth.py `login_alias()` + Scenario "/login redirects to /auth/login".
- [PASS] CSRF via Flask-WTF preserved — templates/login.html retains `<input type=hidden name=csrf_token>`.
- [PASS] /sprints auth-gated: anonymous → /auth/login; authenticated → 200 — routes/main.py `spints()` calls require_login(); public catalog untouched at /topics.
- [PASS] signup semantics untouched — no signup changes in the working tree; builder out-of-scope note holds.

### Files changed by the builder (checked)
- routes/auth.py — login credential validation, generic error copy, /login alias.
- templates/login.html — password field (required, autocomplete=current-password) + email required.
- routes/main.py — /sprints now auth-gated via require_login() (public catalog stays /topics).
- tests/features/auth-hardening.feature — the spec (not edited by verifier).
- tests/steps/action_steps.py — "I sign in with email X and password Y" (MaybeEmpty parse type), session-leak probe, redirected-to-login steps.
- tests/live_db_adapter.py — Supabase client detached from g before app-context pop; explicit close in reset_live_adapter.
- tests/environment.py — cohort seeding adopts existing active cohort.
- tests/features/api.feature, tests/features/landing.feature — password-aware login steps + new error copy.

## Step 3 — full-suite regression (PENDING)

Not yet run. Next action: `.venv/bin/python -m behave > uat/reports/verify-full-run.log 2>&1` and classify baseline vs new failures.

Baseline (uat/reports/behave-full-run1.log, 2026-09-08): 5 features passed, 15 failed; 145 scenarios passed, 58 failed, 7 errored.

## Step 4 — status board

- Builder task: uat/TASKS/bugfix-auth.md
- Builder report: uat/reports/bugfix-auth.md
- This verifier task: uat/TASKS/verify-auth-fix.md (IN PROGRESS — Step 1 + 2 written; Step 3 pending)

## Open concern (not a defect in this fix)

- Signup users still get a random unknown password (secrets.token_urlsafe(16)) and therefore cannot sign back in without that password — builder's out-of-scope caveat. Not introduced by this fix; not blocking BUG-1/2/3.

Status board to append after this verification:
  [test] 2026-09-11T09:17Z verify-auth-fix: auth-hardening 7/7 green; full-suite pending — VERDICT CONFIRMED CORRECT so far


## Context
- Repo: /home/dhruba/Documents/exp_money/daily_learning_freelance/sprint-platform (branch sprint-platform)
- Live app: https://freelancelaunch.onrender.com (Render — do NOT deploy; that's Dhruba's call)
- The BUILDER agent already fixed UAT Area-1 bugs in the WORKING TREE (uncommitted). Task: uat/TASKS/bugfix-auth.md · Builder report: uat/reports/bugfix-auth.md · Status board: uat/STATUS.md
- Your job is INDEPENDENT VERIFICATION ONLY. You are not here to fix anything — you check whether the builder's fix is actually correct and complete, run the suite, and report with evidence. If you find a bug, REPORT it (with file:line + repro), do not patch it.
- Tests run against the LIVE Supabase test DB (tests/live_db_adapter.py). Do not mock Supabase.

## The three bugs under verification
1. BUG-1 (BLOCKER, was): routes/auth.py login handler set session["user_id"] from an email lookup with NO credential check — anyone knowing an email could sign in. Fix claimed: password validated via sb.auth.sign_in_with_password({"email":..., "password":...}); session only set on success; single generic "Invalid email or password." for wrong password OR unknown email (never reveals which).
2. BUG-2 (MINOR): /login 404'd for humans. Fix claimed: /login → /auth/login redirect alias.
3. BUG-3 (MINOR): empty-email submit showed misleading "No account found..." flash. Fix claimed: "Enter your email address to sign in." + required attr on email input.

## Working-tree files changed by the builder (verify each is coherent with the spec)
- routes/auth.py — login credential validation, generic error copy, /login alias
- templates/login.html — password field (required, autocomplete=current-password), email required
- routes/main.py — /sprints now auth-gated via require_login() (public catalog stays /topics)
- tests/features/auth-hardening.feature — THE SPEC (written before the fix; do not edit)
- tests/steps/action_steps.py — "I sign in with email X and password Y" (MaybeEmpty parse type), session-leak probe, redirected-to-login steps
- tests/live_db_adapter.py — adapter's Supabase client detached from g before app-context pop; explicit close in reset_live_adapter
- tests/environment.py — cohort seeding adopts existing active cohort (cooperative with live rotation)
- tests/features/api.feature, tests/features/landing.feature — password-aware login steps + new error copy

## Steps (BDD-first, evidence-first)
Step 0 — read first, never guess:
  cat tests/features/auth-hardening.feature
  cat routes/auth.py | head -120
  cat templates/login.html
  cat routes/main.py | head -120
  git diff --stat   (confirm scope of the working tree)

Step 1 — targeted suite (the spec must be green):
  .venv/bin/python -m behave tests/features/auth-hardening.feature
  Expected: 7 scenarios passed, 0 failed, 0 errored (~34 steps). Record the exact counts.

Step 2 — code review against spec (report PASS/FAIL per check):
  - login POST: empty email → 200 + "Enter your email address to sign in." (BUG-3)
  - login POST: empty OR wrong password, OR nonexistent email → 200 + "Invalid email or password." — one generic message, nothing revealing which part failed (BUG-1)
  - login POST: correct password (demo@sprint-platform.local / demo-password-123) → 302 /sprints + session user_id = real auth.users UUID
  - session cookie hygiene: failed login must not leave an authenticated session
  - /login GET → redirect to /auth/login (BUG-2)
  - CSRF via Flask-WTF preserved; no removed csrf_token in login.html
  - /sprints auth-gate: anonymous → redirect to /auth/login; authenticated → 200 (matches spec + robots.txt policy; public catalog /topics still public)
  - signup semantics untouched (builder said out of scope — confirm no signup changes in the diff)

Step 3 — full-suite regression (this is the part the builder left PENDING):
  .venv/bin/python -m behave > uat/reports/verify-full-run.log 2>&1
  NOTE: this takes ~30 min and runs against the live test DB. Let it finish.
  Baseline from the pre-fix run (uat/reports/behave-full-run1.log, 2026-09-08): 5 features passed, 15 failed; 145 scenarios passed, 58 failed, 7 errored.
  For the new run, report: features passed/failed, scenarios passed/failed/errored.
  Then CLASSIFY the failures: which are pre-existing (present in the baseline, same cause — e.g. LLM-dependent content/gates scenarios) vs NEW regressions caused by the auth change (e.g. landing renders without auth, login-related steps in landing.feature/full-journey.feature/ui-ux.feature). For each NEW regression, capture the failing scenario + first assertion error (file:line).
  Do not fix anything. Do not re-run single features to "make it green" — report what the suite says.

Step 4 — report to uat/reports/verify-auth-fix.md (INCREMENTAL: write the file after Step 1 and Step 2 immediately, append the Step 3 results when they land):
  - RED/GREEN verdict per bug: BUG-1 fixed? BUG-2 fixed? BUG-3 fixed? (evidence: scenario names + counts + code-review PASS/FAIL per check)
  - auth-hardening counts (7 scenarios?)
  - Full-suite numbers vs baseline + failure classification (pre-existing vs regression, with counts)
  - Any correctness concerns (e.g. signup users with random unknown passwords can't sign in again — note if still true and whether it matters)
  - Verdict line at the top: "VERDICT: CONFIRMED CORRECT / ISSUES FOUND — <one line>"
  After writing, append one line to uat/STATUS.md:
  [test] <timestamp> verify-auth-fix: <one-line verdict>

## Hard rules
- NO code edits whatsoever (no routes/, no templates/, no tests/, no .env). Verification only.
- NO commits, NO pushes, NO deploys.
- Stop after 3 identical failures and write what's blocked in the report instead of looping.
- Work autonomously; every deliverable write is incremental, never one big write at the end.