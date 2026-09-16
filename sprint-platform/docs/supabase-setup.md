# Supabase Setup — dedicated project for the Sprint Platform

> **Rule: the Sprint Platform uses its OWN Supabase project.** It must never share a
> database with the v1 FreelanceLaunch app. `db/schema.sql` enforces this with a
> guard that aborts if v1 tables are detected.

## Why a separate project
The new schema **collides by name** with v1 tables:

| Collision | v1 schema.sql / schema_v2.sql | Sprint Platform |
|---|---|---|
| `cohorts` | v1 cohorts (topic-scoped) | sprint cohorts (cluster-scoped, batch dates) |
| `contracts` | v1 contract tracker (pipeline_id FK) | sprint-scoped contracts |
| `sprints` | v1 sprint track tables | sprint platform sprints |
| `proposals` | v1 sprint proposals | sprint platform proposals |
| `job_feed` | v1 sprint job feed | sprint platform job feed |
| `badges` / `mentor` | v1 sprint tables | sprint platform badges / mentor_sessions |

Same names, different shapes → applying both to one database = corruption.

## 1. Create the new project
1. Go to [supabase.com](https://supabase.com/dashboard) → **New project**.
2. Name it e.g. `sprint-platform-<env>` (dev / prod). Do NOT select the v1 project.
3. Note the **Project URL** and the **anon** + **service_role** keys
   (Project Settings → API).
4. Save them to `.env` (copy from `.env.example`).

## 2. Apply the schema
1. Open the new project's **SQL Editor**.
2. Paste the contents of `db/schema.sql` and run.
3. The guard at the top will **abort with an exception** if it detects v1 tables —
   if that happens, you are in the wrong project.
4. Verify: the tables `sprints`, `job_clusters`, `proposals`, `contracts`,
   `badges`, `mentor_sessions`, and the view `public_freelancers` exist.

## 3. Auth
- Enable **Email** provider under Authentication → Providers.
- (Later) add Google/GitHub when the client-facing profile needs it.

## 4. Connection checklist (before any app code)
- [ ] `SUPABASE_URL` points to the **new** project (not `freelancelaunch`'s)
- [ ] `SUPABASE_SERVICE_ROLE_KEY` is the **new** project's key
- [ ] `db/schema.sql` ran cleanly in the new project
- [ ] `select * from sprints limit 1;` returns "0 rows" (not "relation does not exist")

## 5. Passwordless sign-in — dashboard setup (OTP + social)

The app code for email-OTP + Google/Facebook is done; **everything in this section is
outside the repo and has to be clicked in the dashboard.** The previous attempt
(`acfbb9b`) was fully coded and still failed in production for exactly these reasons, so
treat this as release-blocking, not optional.

Measured on this project on 2026-09-15 via `GET /auth/v1/settings` — this is the "before"
picture (see `docs/superpowers/spikes/2026-09-15-t1-pkce-otp-spike.md` §4):

| setting | value today | consequence |
|---|---|---|
| `external.email` | enabled | OTP send/verify works |
| `external.google` / `.facebook` | **disabled** | social buttons must stay off |
| `site_url` | **not set** | OAuth has no canonical origin |
| `uri_allow_list` | **empty** | any `redirect_to` is rejected |
| `smtp_admin` | **not set** | built-in SMTP ≈ 2 mail/hr → OTP unusable under any real load |
| `disable_signup` | false | ✅ new accounts may be created by OTP |
| `mailer_autoconfirm` | false | ✅ verification is genuinely enforced |

Do these in order:

1. **Authentication → URL Configuration**
   - *Site URL*: `https://freelancelaunch.onrender.com`
   - *Additional redirect URLs*:
     `https://freelancelaunch.onrender.com/auth/oauth/callback` and
     `http://localhost:5000/auth/oauth/callback`
   - Both must match `PUBLIC_BASE_URL` in the environment **exactly**, or the callback is
     refused with a `redirected to the site url` style error rather than a clean 4xx.
2. **Authentication → Providers → Google**: enable, paste the OAuth client ID/secret from
   Google Cloud Console (OAuth consent screen: *External*; authorized redirect URI =
   `https://<project-ref>.supabase.co/auth/v1/callback`).
3. **Authentication → Providers → Facebook**: same, but it needs **Meta app review**
   before real users can use it. Until then run with `OAUTH_PROVIDERS=google` on Render —
   the app hides the button; the code path exists, so appending `,facebook` later is the
   whole rollout (no redeploy).
4. **Authentication → One-time tokens (OTP)**: note the **OTP length**. This project
   issues **8-digit** codes, not 6 — the design doc said 6 and is wrong about that. Keep
   `Config.OTP_CODE_LENGTH` / the env override matching what you see here, since it drives
   the code-entry field's `maxlength`.
5. **Authentication → Email → Templates → Magic link**: replace `{{ .ConfirmationURL }}`
   with `{{ .Token }}`. That single change is what makes GoTrue deliver a numeric code
   instead of a link; the same `sign_in_with_otp` call serves both, and
   `verify_otp({email, token, type: "email"})` is the only literal that verifies it
   (`"magiclink"` is rejected).
6. **Authentication → SMTP**: configure Brevo or Resend (free tier) with a verified sender
   domain — SPF/DKIM must pass. Without this the built-in ~2/hr cap is the exact failure
   mode of `acfbb9b`.
7. **Authentication → Rate limits**: keep OTP per email/IP per hour inside the SMTP free
   tier. The app's own 60 s resend cooldown (`OTP_RESEND_COOLDOWN_SECONDS`) is the inner
   belt, not the outer one.

### ⚠️ Two dashboard settings the app's behaviour is coupled to

1. **Do NOT set `disable_signup` (Allow new users to sign up) to OFF while
   `OTP_EMAIL_ENABLED` is on.** The app sends `should_create_user=true`, so
   signup-off makes an *unregistered* address fail while a registered one still
   succeeds — and `routes/auth.py` reports a send failure honestly, so that
   difference becomes a **user-enumeration oracle**. It must be flipped as a
   pair: turn off `OTP_EMAIL_ENABLED` (which makes the password form primary
   again) before disabling signup in the dashboard.
2. **Set Authentication → Rate limits before launch.** Identity creation here is
   unauthenticated **by design** (code-possession is the only gate, and the
   signup funnel exists to make first-run frictionless), and the app's 60s
   resend throttle is *per session cookie* — a caller can reset it by discarding
   cookies, so it is a UX guard, not an abuse control. The only real bound on
   send volume is GoTrue's per-email/per-IP rate limit plus the SMTP free tier.
   Leaving both at defaults makes OTP abusable and can burn the whole SMTP quota.

**Toggling from the app side** (no secrets involved — the provider credentials live here,
never in the repo): `OAUTH_PROVIDERS=google,facebook` and `OTP_EMAIL_ENABLED=true|false`.
`render.yaml` deliberately needs no change for any of this.

## 6. Verifying auth config without sending email

Two of the above steps can be checked before you have SMTP at all, which is how the spike
tested a real code round-trip:

- `GET /auth/v1/settings` (anon key) answers the provider/site-url/smtp questions above.
  Note the supabase-py `auth._request()` returns a **raw httpx `Response`** — call `.json()`.
- `POST /auth/v1/admin/generate_link` (service key) with `{"type":"magiclink","email":…}`
  returns the numeric code in the **`email_otp`** field instead of mailing it, so a code can
  be verified end-to-end offline. ⚠️ A code is **single-use**: spend one fresh token per
  experiment or every "control" after the first verify fails for the wrong reason.
  ⚠️ supabase-py's `GenerateLinkResponse` models only `.user`, so the token fields are not
  reachable through the typed client — read the raw body.
- Throwaway addresses must be syntactically acceptable to GoTrue: `@example.com`,
  `@example.org` and any `@….invalid` are **rejected** as `email_address_invalid`, so an
  unregistered-but-well-formed domain (e.g. `@sprintspike-otp.dev`) is the safe choice.
- If you create users while probing, **delete exactly the ids you created**, enumerated from
  your own run. Never clean up by matching on an email *substring* or a shared domain — that
  is how a spike can eat somebody else's fixture accounts.
- ⚠️ **`admin.delete_user` cascades.** Every `user_id` FK here is
  `ON DELETE CASCADE`, and `sprints` cascades onward to `sprint_days`, `proposals`,
  `contracts`, `badges`, `case_studies`, `capstone_briefs`, `verification_reviews`,
  `sprint_unlock_snapshots` and `mentor_sessions` — 14 tables reachable from one user row.
  So **snapshot the tables you are about to affect first**: a "how much did I destroy?"
  count taken *after* the delete always reads zero and proves nothing.

## Teardown (if you ever stop using it)
- Pause/delete the project from the Supabase dashboard. The v1 project is untouched.
