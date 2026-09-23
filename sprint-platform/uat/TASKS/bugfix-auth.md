# BUG-1 FIX TASK — auth hardening (UAT Area 1 failures)

## Context
- Repo: /home/dhruba/Documents/exp_money/daily_learning_freelance/sprint-platform (branch sprint-platform)
- Live app: https://freelancelaunch.onrender.com (Render, manual deploys — do NOT deploy; that's Dhruba's call)
- UAT Area 1 (auth) verdict: FAIL. Full report: uat/reports/auth.md. Status board: uat/STATUS.md
- Workflow is BDD-first: the feature file tests/features/auth-hardening.feature IS the spec and already exists.
- Tests run against the LIVE Supabase test DB (tests/live_db_adapter.py seeds/creates users via admin API). Do not mock Supabase.

## The bugs
1. BUG-1 (BLOCKER): routes/auth.py login handler (~lines 20-36) looks up user by email and sets session["user_id"] without any credential check. Anyone who knows an email can sign in.
2. BUG-3 (MINOR): empty-email submit on /auth/login shows misleading "No account found..." flash. Spec: "Enter your email address to sign in." Also add required attribute to email input.
3. BUG-2 (MINOR): /login 404s — add a redirect /login → /auth/login.

## What to build (BDD-first: RED → GREEN)
Step 0 — read the failing spec first:
  cat tests/features/auth-hardening.feature
  cat tests/steps/action_steps.py   (login steps + "no session leak" probe already implemented)
  cat routes/auth.py  (the code under fix)

Step 1 — RED: run only the auth feature against the local app:
  .venv/bin/python -m behave tests/features/auth-hardening.feature
  (activate venv first if needed: source .venv/bin/activate)
  Expect failures: wrong-password still authenticates (current code signs in with any password).
  Record which scenarios fail.

Step 2 — GREEN: fix routes/auth.py login handler:
  - Validate password with Supabase: sb.auth.sign_in_with_password({"email": email, "password": password})
    This validates against auth.users. Users seeded with password=X sign in with X.
  - On missing/empty password → flash "Invalid email or password." 200 re-render (see spec scenario "Missing password field is rejected")
  - On wrong password or nonexistent email → flash "Invalid email or password." (do NOT reveal which part failed)
  - On empty email → flash "Enter your email address to sign in." 200
  - On success → session["user_id"] = <auth.users uuid>, redirect /sprints
  - Keep CSRF via Flask-WTF as-is.
  - /login route: add redirect to /auth/login (BUG-2).
  - templates/login.html: add required + type=email on the email input; add a password field — wait: the spec signs in with email+password, so the form must POST a password. Add a password input (name="password") with required.
  - Signup creates users with a random password (secrets.token_urlsafe(16)) — leave signup semantics alone (out of scope), but the user it creates CAN log in later only if they know the random password. That's acceptable for now; do not change signup flow.

Step 3 — verify local:
  .venv/bin/python -m behave tests/features/auth-hardening.feature   → all 7 scenarios green
  Then run the FULL suite to catch regressions:
  .venv/bin/python -m behave
  If a pre-existing test breaks because it relies on email-only login (e.g. tests/steps/common_steps.py _login helper, landing.feature, full-journey.feature), update that helper/step to pass the seeded user's password (from tests/live_db_adapter.py or seed_live.py: demo@sprint-platform.local/demo-password-123, admin@sprint-platform.local/admin-pass-123). Keep changes minimal.

Step 4 — report back (write to uat/reports/bugfix-auth.md):
  - Scenarios red before / green after (counts)
  - Full-suite result (passed/failed)
  - Files changed with one-line purpose each
  - Anything left open (e.g. signup random-password caveat)

## Rules
- No template content fallbacks; no mocking the live DB adapter.
- Don't touch .env or credential files. Don't commit, push, or deploy.
- If a step fails 3 times the same way, stop and write what's blocked in the report instead of looping.
- Work autonomously; when done append a line to uat/STATUS.md:
  [builder] <timestamp> BUG-1/2/3 fix: <one-line result>
