# UAT AREA 1: AUTH — VERDICT: FAIL (1 major/security defect; all other criteria PASS)

Target: https://freelancelaunch.onrender.com | Creds: admin@sprint-platform.local / admin-pass-123
Method: visible Chrome 142 on DISPLAY=:0 via CDP :9222 (non-headless confirmed: no --headless flag), plus curl HTTP matrix. JS console: 0 errors on all pages. No destructive actions performed.
Tested by: tester agent session 20260907_225540_55251c, 2026-09-07 23:05–23:44

DEVIATION vs PLAN: live login route is /auth/login, NOT /login. /login returns 404 (Render error page). All plan references to "login page" were executed against /auth/login. /dashboard/ is a 302 redirector to /sprints (routes/main.py:339-345) — the authenticated landing surface IS the /sprints picker.

## T1. Login page render + CSRF — PASS
- GET /auth/login → HTTP 200, title "Sign in — FreelanceLaunch sprint platform", h1 "Sign in to your sprints"
- Inputs: csrf_token:hidden, email:email. NO password field exists anywhere on the form (live DOM + template login.html:20-27 + curl of live HTML)
- CSRF token present: 91-char Flask-WTF signed token (IjQyZjFj...)
- Screenshot: uat/screenshots/01-login-page.png

## T2. Wrong credential — SPLIT RESULT
- T2a nonexistent email nobody-wrong@nonexistent.example: HTTP 200, login re-rendered with flash "No account found for that email on this project." No 500, no redirect-as-success. Verified in real Chrome (JS form fill + submit + DOM flash check) AND curl. PASS
- T2b seeded email + WRONG password (password=totally-wrong-pass, injected — field absent from UI): HTTP 302 → /sprints WITH session cookie set (len 170). FAIL — see BUG-1.
- Screenshot: uat/screenshots/02-wrong-credential-error.png (flash state)

### BUG-1 — Password is never validated (auth = email-only)
- Page: /auth/login. Element: login form / POST handler routes/auth.py:20-36
- Expected: wrong password → error, no session. Actual: arbitrary/absent password → 302 /sprints + authenticated session
- Repro: POST /auth/login with valid CSRF + Referer, email=admin@sprint-platform.local, password=anything → 302, session cookie issued
- Root cause: handler looks up user by email and sets session without any credential check (code + live behavior confirmed)
- Severity: MAJOR per plan rubric ("wrong-password shows success/state leak") — tester recommends elevating to BLOCKER pre-launch: anyone who knows an email address can sign in as that user
- Evidence: curl T2b output (HTTP 302 → /sprints, session cookie len 170); routes/auth.py:25-35

## T3. Seeded admin login — PASS
- POST /auth/login (email-only, UI-equivalent): HTTP 302 → https://freelancelaunch.onrender.com/sprints, session cookie set (len 170)
- Real Chrome: landed /sprints, title "Choose your sprint — demand-validated topics on FreelanceLaunch", h1 "Choose your sprint", Sign out link present = authenticated
- Screenshot: uat/screenshots/03-post-login-picker.png

## T4. /dashboard/ with session — PASS
- HTTP 302 → /sprints (redirect-to-picker as designed)

## T5. Logout clears session — PASS
- GET /auth/logout with session: HTTP 302 → /
- Real Chrome: clicked Sign out link → landed on landing page, Sign out link gone, login/signup state restored
- Server-side invalidation confirmed: post-logout navigation to /dashboard/ redirects to /auth/login (cookie alone no longer authenticates)
- Note: Flask issues a fresh anon session cookie (len 111) rather than clearing the cookie — standard, user_id removed. Not a bug.
- Screenshot: uat/screenshots/04-logged-out-landing.png

## T6. Anonymous /dashboard/ — PASS
- HTTP 302 → /auth/login (curl + real Chrome navigation landed on login)
- Screenshot: uat/screenshots/05-anon-redirect-to-login.png

## T7. Anonymous /mentor — PASS: HTTP 302 → /auth/login

## T8. CSRF enforcement — PASS
- POST /auth/login with valid CSRF + Referer: accepted (302/200 per credential path)
- POST without CSRF: HTTP 400. POST with tampered CSRF: HTTP 400
- POST without Referer header: HTTP 400 "The referrer header is missing" (Flask-WTF HTTPS origin check — browsers always send Referer, no user impact)

## Additional exhaustive findings
- BUG-2 (MINOR): /login 404s. Nothing in the app links to /login (grep of templates), user impact ~none, but plan/BRIEF wording assumes /login — docs/spec mismatch.
- BUG-3 (MINOR): empty-email submit → "No account found for that email on this project." — misleading copy; email input lacks required attribute (verified: required=false, type=email). Server returns 200 + flash for empty string.
- Signup page /auth/signup renders (title "Create your free account", CSRF present, inputs display_name + email, Sign-in link back). Screenshot: 06-signup-page.png
- Session cookie is HttpOnly (not readable via document.cookie) — correct hardening
- Limitation: vision-analysis backends failed all session (gateway 503 + malformed-request 400s), so no AI visual commentary; screenshots were still captured at every step for human review, and all claims are backed by DOM assertions / HTTP statuses

## Screenshots on disk (uat/screenshots/)
01-login-page.png, 02-wrong-credential-error.png, 03-post-login-picker.png, 04-logged-out-landing.png, 05-anon-redirect-to-login.png, 06-signup-page.png

## Recommendation
Per the plan's own rubric, area 1 does not pass: wrong-password showing success is the named failure mode. Fix routes/auth.py login to validate credentials before the next UAT area depends on it.
