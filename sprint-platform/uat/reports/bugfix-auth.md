# BUG-1/2/3 FIX REPORT — auth hardening (UAT Area 1)

Fix branch: sprint-platform (working tree, uncommitted) · 2026-09-09
Spec: tests/features/auth-hardening.feature (BDD-first — written before the fix)
Live DB: real Supabase test project (no mocks).

## RED → GREEN

- RED evidence: UAT area-1 report (uat/reports/auth.md) — live curl POST with
  valid email + arbitrary password returned 302 → /sprints with an authenticated
  session (BUG-1). The in-session behave RED run was blocked by a harness error
  ("Cannot send a request, as the client has been closed" in before_all), which
  was fixed before GREEN verification (see harness changes below).
- GREEN: `.venv/bin/python -m behave tests/features/auth-hardening.feature`
  → 7 scenarios passed, 0 failed (34 steps) in 3.0s. All 7:
  wrong-password rejected, missing-password rejected, nonexistent-email generic
  error, empty-email clear copy, failed-login no session leak + /sprints redirect,
  correct-password signs in (302 /sprints), /login → /auth/login redirect.

## Full-suite regression

- PENDING (run in progress — this section updates when it lands)

## Changes

- routes/auth.py — login now validates credentials via
  sb.auth.sign_in_with_password (Supabase auth.users); session["user_id"] set
  only on success. Empty email → "Enter your email address to sign in.";
  empty/wrong password or unknown email → one generic "Invalid email or
  password." (never reveals which part failed). Added /login → /auth/login
  redirect alias (BUG-2).
- templates/login.html — added password field (required,
  autocomplete=current-password); email input gets required attr (BUG-3).
- routes/main.py — /sprints is now auth-gated (require_login) to match the
  auth-hardening probe + robots.txt policy; public crawler catalog is /topics.
- tests/steps/action_steps.py — new step "I sign in with email X and password Y"
  (MaybeEmpty parse type so empty quoted values match); session-leak probe and
  redirected-to-login steps.
- tests/live_db_adapter.py — adapter's Supabase client detached from g before
  app-context pop (fixes "client has been closed"); explicit client close in
  reset_live_adapter.
- tests/environment.py — cohort seeding is cooperative with the live site's
  bi-weekly cohort rotation (adopts existing active cohort instead of fighting
  the partial unique index).
- tests/features/api.feature, landing.feature — updated to password-aware login
  steps and new error copy.

## Open caveats

- Signup still creates users with a random unknown password
  (secrets.token_urlsafe(16)) — signup users can't sign in again until a
  password/magic-link flow is added. Out of scope here; product decision needed.
- Live site (Render) NOT deployed — manual deploys are Dhruba's call. UAT area-1
  re-test must wait for the deploy.
