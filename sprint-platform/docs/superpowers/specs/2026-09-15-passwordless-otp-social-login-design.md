# Design — Passwordless Email OTP + Social Login (Google/Facebook), $0 stack

- **Date:** 2026-09-15
- **Branch:** `feature/passwordless-otp-social-login` (snapshot of pre-change state: `before_login_changes` @ f3face8)
- **Status:** awaiting user review
- **Constraints:** $0/month operating cost; server-rendered Flask (no JS auth state); keep existing session contract

## 1. Goal & non-goals

Replace the unverified email-only auth (which allows account and admin takeover) with
passwordless **email OTP** as the primary flow, plus **Google and Facebook OAuth**
buttons, all routed through the existing Supabase Auth project.

Non-goals (explicitly deferred):
- **Phone/SMS OTP** — architecturally prepared (same send/verify shape), but requires paid
  Twilio/MessageBird + India DLT compliance. Revisit only with a budget.
- **Apple Sign-In** — requires $99/yr Apple Developer Program. Out on the $0 constraint.
- **X/Twitter, LinkedIn** — free-tier caps/policy volatility; the provider allow-list makes
  them config+test additions later, no rework.
- Profile editing (does not exist today), admin-gate refactor, LLM/mentor issues (separate track).

## 2. Current state (verified on disk, supabase-auth 2.31.0 introspected)

- Identity store: Supabase `auth.users` (UUID) via `supabase==2.31.*`.
- Session: Flask signed cookie `session["user_id"]` → `load_user` (app.py:101, UUID-validated,
  loads `user_profiles` into `g.user`, tolerates missing profile row) → `require_login`
  (routes/\_\_init\_\_.py:46) gates ~31 handlers. **This contract does not change.**
- `services/supabase_client.py`: request-scoped clients; `get_supabase()` = service-role,
  `get_client_supabase()` = anon; teardown closes sessions for attrs `supabase`, `client_supabase`.
- `routes/auth.py` today:
  - login (l.23): email+password via `sign_in_with_password` (generic errors) ✅ already fixed in f3face8;
  - signup (l.65): email+name only; **existing-email collision auto-logs-in (l.79–82)** ← takeover + admin-takeover hole; new users get a **random unknown password** with `email_confirm: True` ← login/signup mismatch strands accounts after logout.
- Client API surface (verified): `sign_in_with_otp`, `verify_otp`, `resend`,
  `sign_in_with_oauth`, `exchange_code_for_session({auth_code, code_verifier, redirect_to})`,
  `get_user`. `SyncClientOptions` accepts `flow_type` + `storage`.
- Email OTP vs magic link is **template-driven**: with `{{ .Token }}` in the Supabase
  "Magic link" email template, GoTrue sends a 6-digit code; the Python client's email body
  is allow-list built (no `email_otp` flag needed/leaked). Verify: `verify_otp({email, token, type:"email"})`.
- History: `acfbb9b` reverted a prior OAuth+magic-link attempt. Root causes were **dashboard
  config** (Site URL unset, provider disabled, built-in SMTP ≈2/hr) — none are code limits,
  and OTP needs no redirect at all.

## 3. Decisions approved during brainstorming

1. $0 combo: OTP backbone (email-first, phone-ready) + Google + Facebook via **Supabase Auth**
   (approach A, server-side). Fallback if PKCE glue fights us: frontend-initiated OAuth (B) — no other design change.
2. Password login stays for accounts that have real passwords; OTP is the primary CTA; signup
  collision auto-login is deleted.
3. SMTP provider (Brevo or Resend free tier) configured in the **Supabase dashboard** — zero app secrets.

## 4. Architecture

```
GET  /auth/login            unified sign-in page
POST /auth/otp/send    ──► sb_auth.sign_in_with_otp({email, options:{should_create_user:true}})
        60s resend cooldown stored in Flask session; always generic "code sent" response
POST /auth/otp/verify  ──► sb_auth.verify_otp({email, token, type:"email"})
        success → session["user_id"] = user.id → provision user_profiles if new → /sprints
GET  /auth/oauth/<provider> (allow-list: google|facebook)
      ──► sign_in_with_oauth on pkce client (code verifier → FlaskSessionStorage) → 302 provider
GET  /auth/oauth/callback?code=
      ──► exchange_code_for_session({auth_code, code_verifier, redirect_to}) → same post-auth step
POST /auth/login (kept)      email+password → sign_in_with_password (unchanged semantics)
GET  /auth/signup            renders login page in "create account" mode (single surface)
/auth/logout, /login alias   unchanged
```

Both OTP verify and OAuth callback funnel into one helper `_complete_auth(uid, email, name_hint)`:
set `session["user_id"]`, upsert `user_profiles` if no row (display_name = name_hint / provider
name / email prefix; `is_public: False`), welcome flash. This makes new-account provisioning
identical across all three entry paths and fixes the admin@ missing-profile quirk for future signups.

## 5. Detailed changes

### 5.1 `services/supabase_client.py`
- Add `FlaskSessionStorage` (dict get/set/delete keyed by the client's `storage_key`, persisted
  in `flask.session["_sb_pkce"]`) — implements the supabase-auth storage protocol
  (import path to be pinned in impl spike; duck-typed get/set/delete otherwise).
- Add `get_auth_supabase()`: anon-key client created with
  `create_client(url, anon_key, options=SyncClientOptions(flow_type="pkce", storage=FlaskSessionStorage(), persist_session=False, auto_refresh_token=False))`,
  cached on `g.auth_supabase`; register that attr in `close_request_clients()`.
- Existing two clients untouched (service-role keeps `admin.list_users` etc.).

### 5.2 `routes/auth.py`
- DELETE collision auto-login (l.79–82). `signup` POST becomes a funnel into `otp_send` (keeps
  URL/anchors working); `display_name` from signup rides in a pending-session field consumed by `_complete_auth`.
- New: `otp_send`, `otp_verify` (email + token form), `oauth_start`, `oauth_callback`, `_complete_auth`.
- OAuth state/errors: missing/denied `code` or exchange failure → flash generic
  "Social sign-in didn't complete — try the email code." on `/auth/login`.
- Cooldown: `session["otp_last_sent_at"]`; ≤60s → resend refused, UI shows countdown (server-side
  check authoritative; `resend` endpoint not exposed separately). Supabase dashboard rate-limits
  are the outer belt; SMTP free-tier caps bound total sends.
- No error message ever reveals whether an email exists (send always reports success).

### 5.3 `config.py` / env
- `OAUTH_PROVIDERS = os.getenv("OAUTH_PROVIDERS", "google,facebook")` (validated lowercase set);
- `OTP_EMAIL_ENABLED = os.getenv("OTP_EMAIL_ENABLED", "true")`;
- redirect_to base derived from existing `PUBLIC_BASE_URL` (prod + localhost dev value).
- `.env.example`: document the two new optional vars. `render.yaml`: **no changes** (all secrets
  stay in Supabase dashboard; providers toggled by env only if we later add X/LinkedIn).

### 5.4 Templates
- `login.html`: primary block "Email me a sign-in code" (email + Continue), collapsible
  "Use my password instead" (current form, unchanged action), provider buttons
  `Continue with Google / Facebook` (icons via existing design tokens), then a code-entry step
  (same page, `?step=code`, showing masked email + resend link).
- `signup.html`: becomes `{% extends %}` thin redirect to login in create mode (first name field
  kept there; links from sprints page stay valid).
- `templates/magic_sent.html` — not re-created; OTP is code-entry, no "check your inbox" interstitial beyond the step.

### 5.5 Admin-gate note
`_require_admin` (routes/admin.py:16) unchanged functionally; the signup collision removal kills
its exploit path. Hardcoded admin email constant stays as a known cleanup item (out of scope here).

## 6. Supabase dashboard setup checklist (one-time; the piece that was missing in acfbb9b)
1. Authentication → URL Configuration: **Site URL** `https://freelancelaunch.onrender.com`;
   Additional redirect URLs: `https://freelancelaunch.onrender.com/auth/oauth/callback`,
   `http://localhost:5000/auth/oauth/callback`.
2. Providers → Google: enable, client ID/secret from Google Cloud OAuth consent (External, prod URL
   as authorized redirect: `https://<project>.supabase.co/auth/v1/callback`).
3. Providers → Facebook: needs Meta app review before production use. Until review passes,
   `OAUTH_PROVIDERS=google` on Render (button hidden); the code path exists and FB flips on by
   appending `,facebook` to the env var — no deploy needed. Local/dev may enable it early for testing.
4. Email → Templates → **Magic link**: replace `{{ .ConfirmationURL }}` with `{{ .Token }}`
   (6-digit code UX); keep subject wording.
5. Auth → Rate limits: OTP email per email/IP per hour within SMTP free tier (Brevo ~300/day,
   Resend ~3k/mo — verify current numbers at setup).
6. Configure custom SMTP (Brevo/Resend) + verify SPF/DKIM on the domain. Without this, built-in
   SMTP (~2/hr) makes OTP unusable — the exact failure from the last attempt.

## 7. Security outcomes & residual risks
**Closes:** unverified-email impersonation; admin auto-login via signup collision; magic-link
click dependency (code-entry has no redirect); stranded random-password accounts (OTP logs them
in via their confirmed email).
**Residual (accepted for v1):** OAuth code exchange requires correct redirect allow-list (test in
staging before enabling button); Supabase free-tier SMTP caps = soft DoS under abuse (mitigated
by dashboard rate limits + cooldown); session cookie has no absolute expiry (existing behavior —
unchanged, flagged separately); X/LinkedIn/Apple deliberately not promised.

## 8. Migration & compatibility
- Legacy email-only accounts (random password, `email_confirm=True`): OTP log-in works
  immediately — identity keyed on email; no data migration.
- OAuth first-login for an existing email: Supabase links provider to the existing verified-email
  user automatically; no custom logic; one integration test asserts no duplicate row.
- `verify_dogfood_fixes.py` §7 (asserts email-only login flow): updated to the new primary path.
- Deploy order keeps old password form working at every step — no big-bang cutover.

## 9. Testing
- Unit (pytest, in `tests/`): otp_send sets cookie + calls sign_in_with_otp (client faked);
  resend cooldown enforced; otp_verify happy/wrong-code/expired; _complete_auth provisions
  user_profiles once; collision signup no longer sets session; oauth_start only allow-listed
  providers; callback missing-code path.
- Integration (live project, manual/dogfood): localhost with built-in SMTP (2/hr OK for tests);
  one full code round-trip; Google button round-trip on Render before enabling FB.
- Existing suite: behave journeys + verify suite green (was 21/21 at f3face8).
- Pre-impl spike (30 min, partially done): venv rebuilt ✅; API surface verified ✅; remaining:
  storage protocol import path + `verify_otp` accepted `type` literals ("email" vs "signup")
  against the live project — gates §5.1/§5.2 implementation day 1.

## 10. Implementation order (feeds the plan)
1. Spike finish (storage protocol, verify type literal) → 2. config.py + .env.example →
3. supabase_client.py (`FlaskSessionStorage`, `get_auth_supabase`, teardown) → 4. auth.py OTP
routes + `_complete_auth` + signup hole removal → 5. templates (login OTP+step, signup funnel) →
6. unit tests → 7. dashboard setup (section 6) → 8. OAuth routes + buttons → 9. live verification
on localhost then Render → 10. dogfood suite update.

## 11. Verified facts appendix (supabase-auth 2.31.0, this venv)
`sign_in_with_otp(credentials)` → AuthOtpResponse; email body allow-listed:
`{email, data, create_user, gotrue_meta_security}` + `redirect_to`.
`verify_otp(VerifyEmailOtpParams{email, token, type})` → AuthResponse; union includes
`VerifyTokenHashParams{token_hash, type}` (future magic-link option).
`sign_in_with_oauth`; `exchange_code_for_session({code_verifier, auth_code, redirect_to})`.
`SyncClientOptions{schema, headers, auto_refresh_token, persist_session, flow_type, storage, ...}`.
Template mechanism: `{{ .Token }}` ⇒ OTP; `{{ .ConfirmationURL }}` ⇒ magic link (docstring, verbatim).
