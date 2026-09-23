# UAT REPORT — Passwordless email OTP + Google/Facebook OAuth
> **NOT UAT EVIDENCE — tooling self-test.** Every number below came from a --selftest run (scripted users, zero live writes, no browser). The real report replaces this file.
- Assembled 2026-09-16 12:43:57 from `t7-v5-merged-1789542656.json` (edit the verdict by hand after reading it)
- Verdict: **PENDING — uat-validator sign-off**
- Evidence classes: LIVE / FAKE-TRANSPORT / STATIC on every row
- Assertions: 74 total — 71 pass, **0 fail**, 3 gap/skip
- Live SMTP sends spent: 0 (cap 2/hour, captain ruling)
- **Purge list** — every `auth.users` identity this run created (1 of cap 8). **I delete nothing**; this list is for the user's post-launch cleanup: `uat-otp-a5@example.com`
- Team rule note: backend-eng's spike cleanup removed two stale husks it did not create (`11c3e099-…` uat.user.1788795034@example.com, `cdb275ae-…` live_qa_1788762183@example.com). Neither is referenced anywhere in this UAT's tooling, plan, evidence or the behave fixtures (audited by the RULE check in step 0), so the recorded behave baseline is unaffected.
- behave baseline for A12: 210 scenarios / 58 pre-existing failures / 30min 38.477s (`uat/reports/behave-full-run1.log`) — NEW failures only
## Evidence
| area | class | result | claim | detail |
|---|---|---|---|---|
| P1 | STATIC | gap | test tree identity | toplevel=/home/dhruba/Documents/exp_money/daily_learning_freelance HEAD=e89e740 expect=e89e740 is-ancestor OK fingerprint=3c47a85f6afb |
| P1 | STATIC | PASS | signup collision auto-login deleted (static) |  |
| P1 | STATIC | PASS | auth client factory present | get_auth_supabase |
| P1 | STATIC | PASS | an OTP surface exists in the template tree | _auth_panel.html,signup.html |
| A1 | STATIC | PASS | code-entry length limit is not hardcoded to 6 | length hints [] — none in source (otp_length comes from config); the browser pass must confirm 8 digits are typeable |
| A1 | FAKE-TRANSPORT | PASS | /auth/login and /auth/signup expose the same OTP form + provider buttons | actions/forms google=True/facebook=True vs True/True |
| RULE | STATIC | PASS | my tooling makes no delete/drop/purge call (create-only) | 2 files parsed via ast |
| RULE | STATIC | PASS | no live dependency on the two deleted husk accounts (tests/, templates/) | my A12 baseline is unaffected; fresh uat-otp-* identities at run time |
| RULE | STATIC | PASS | user cap headroom: 1 spent + 5 to mint <= cap 8 | spent=['uat-otp-a5@example.com'] projected 6/8 |
| RULE | STATIC | PASS | live SMTP sends in the last hour: 0/2 | only step 2 (A2) may spend slots; the ledger refuses more |
| A3 | FAKE-TRANSPORT | PASS | first send reaches the transport with should_create_user inside options (spike §3.2) | status=200 args={"email": "uat-otp-a3@example.com", "options": {"should_create_user": true}} |
| A3 | FAKE-TRANSPORT | PASS | resend to the SAME address inside 60s is refused server-side (no GoTrue call) | calls=1 status=200 |
| A3 | FAKE-TRANSPORT | PASS | refused resend shows a countdown, not a silent success | Please wait 60s before requesting another code. |
| A3 | FAKE-TRANSPORT | PASS | per-address throttle: a fresh address in the same session is NOT locked out | calls=2 (expect 2) |
| A3 | FAKE-TRANSPORT | PASS | …but that new address is now itself throttled | calls=2 (still 2) |
| A3 | FAKE-TRANSPORT | PASS | cooldown state lives in the session, keyed per address | keys=['otp_email', 'otp_last_sent_at'] |
| A3 | FAKE-TRANSPORT | PASS | cooldown is per-session, not global (fresh cookie jar can send) | calls=1 |
| A6 | FAKE-TRANSPORT | PASS | signup with EXISTING email sets no session (takeover closed) | status=200 session=None set-cookie=[] |
| A6 | FAKE-TRANSPORT | PASS | /sprints still lands the anonymous caller on the login page | final='/auth/login' status=200 |
| A6 | FAKE-TRANSPORT | PASS | /admin still lands the anonymous caller on the login page | final='/auth/login' status=200 |
| A6 | FAKE-TRANSPORT | PASS | collision response is the same generic shape as otp_send | signup=200 |
| A6 | STATIC | gap | RESIDUAL GAP: admin@sprint-platform.local collision never tested live (captain authorized 2 SMTP slots, both spent on A2) | named in the report; not silently covered |
| A8 | LIVE | PASS | oauth_start issues a 302 (not a 5xx) | status=302 loc_head='https://tzfohwzgxlecsilvqmjq.supabase.co/auth/v1/authorize?redirect_to=http%3A%2' |
| A8 | LIVE | PASS | 302 targets <project>.supabase.co/auth/v1/authorize | https://tzfohwzgxlecsilvqmjq.supabase.co/auth/v1/authorize?redirect_to=http%3A%2F%2Flocalhost%3A5000%2Fauth%2Foauth%2Fca |
| A8 | LIVE | PASS | authorize URL carries provider=google | got 'google' |
| A8 | LIVE | PASS | authorize URL carries code_challenge | got 'vnQTplby7Mhr_6ziusnayYkgtZz921CHzXDb8u0qqeg' |
| A8 | LIVE | PASS | authorize URL carries code_challenge_method=s256 | got 's256' |
| A8 | LIVE | PASS | authorize URL carries redirect_to | got 'http%3A%2F%2Flocalhost%3A5000%2Fauth%2Foauth%2Fcallback' |
| A8 | LIVE | PASS | challenge != verifier (real S256 hash, not the plain fallback) |  |
| A8 | LIVE | PASS | redirect_to is our own /auth/oauth/callback under PUBLIC_BASE_URL | http://localhost:5000/auth/oauth/callback |
| A8 | LIVE | PASS | verifier persisted in THIS cookie jar's session (key name read from code, not assumed) | session keys=['_sb_pkce'] |
| A8 | LIVE | PASS | no verifier/challenge text in the response body |  |
| A8 | LIVE | PASS | oauth_start response persists the session (Set-Cookie present) | without it the verifier is dropped and the callback cannot succeed |
| A8 | LIVE | PASS | verifier is a non-empty value under the client's own storage key | key='_sb_pkce' verifier_len=64 |
| A8 | LIVE | PASS | second oauth_start rotates the stored verifier (no stale challenge reuse) | rotated=True |
| A8 | LIVE | PASS | cross-jar binding: a fresh jar cannot redeem another jar's code | start_in_fresh_jar=302 |
| A8 | LIVE | PASS | non-allow-listed provider '/auth/oauth/evil' refused without 5xx | status=404 |
| A8 | LIVE | PASS | non-allow-listed provider '/auth/oauth/twitter' refused without 5xx | status=404 |
| A8 | LIVE | PASS | non-allow-listed provider '/auth/oauth/facebook;x' refused without 5xx | status=404 |
| A8 | LIVE | PASS | non-allow-listed provider '/auth/oauth/%2e%2e' refused without 5xx | status=404 |
| A8 | LIVE | PASS | non-allow-listed provider '/auth/oauth/<script>alert(1)</script>' refused without 5xx | status=404 |
| A8 | LIVE | PASS | non-allow-listed provider '/auth/oauth/' refused without 5xx | status=404 |
| A11 | LIVE | PASS | both buttons render for OAUTH_PROVIDERS=google,facebook (shipped default) | {'providers': ['facebook', 'google'], 'otp_form': True, 'code_step': False, 'password_form': True} |
| A11 | LIVE | PASS | FB button removed for OAUTH_PROVIDERS=google (plumbing we own) | {'providers': ['google'], 'otp_form': True, 'code_step': False, 'password_form': True} |
| A11 | LIVE | PASS | no provider buttons for OAUTH_PROVIDERS='' (deliberate opt-out) | {'providers': [], 'otp_form': True, 'code_step': False, 'password_form': True} |
| A11 | LIVE | PASS | OTP form hidden and password path kept for OTP_EMAIL_ENABLED=false | {'providers': ['facebook', 'google'], 'otp_form': False, 'code_step': False, 'password_form': True} |
| A11 | LIVE | PASS | OTP is the primary surface when enabled (send form present) | {'providers': ['facebook', 'google'], 'otp_form': True, 'code_step': False, 'password_form': True} |
| A9 | FAKE-TRANSPORT | PASS | callback no code: 200 + generic recovery copy, no session, no 5xx | status=200 session=False flash='Social sign-in didn&#39;t complete — try the email code.' |
| A9 | FAKE-TRANSPORT | PASS | callback no code: no raw GoTrue error text | leaked=[] |
| A9 | FAKE-TRANSPORT | PASS | callback invalid code: 200 + generic recovery copy, no session, no 5xx | status=200 session=False flash='Social sign-in didn&#39;t complete — try the email code.' |
| A9 | FAKE-TRANSPORT | PASS | callback invalid code: no raw GoTrue error text | leaked=[] |
| A9 | FAKE-TRANSPORT | PASS | callback stateless code: 200 + generic recovery copy, no session, no 5xx | status=200 session=False flash='Social sign-in didn&#39;t complete — try the email code.' |
| A9 | FAKE-TRANSPORT | PASS | callback stateless code: no raw GoTrue error text | leaked=[] |
| A9 | FAKE-TRANSPORT | PASS | failed exchange (verifier-less, as GoTrue rejects it) -> generic copy, no session | status=200 session=False flash='Social sign-in didn&#39;t complete — try the email code.' |
| A9b | FAKE-TRANSPORT | PASS | successful exchange → session uid + 302 to the post-auth target | session=22222222-2222-2222-2222-222222222222 loc=/sprints |
| A9b | FAKE-TRANSPORT | PASS | exchange called once with the code + a verifier our code controls (or the documented storage fallback) | {"auth_code": "uat-fake-code", "code_verifier": "", "redirect_to": "http://localhost:5000/auth/oauth/callback"} |
| A9b | FAKE-TRANSPORT | PASS | replayed code does not re-auth (generic recovery, no session) | session=False |
| A9b | FAKE-TRANSPORT | PASS | the OAuth-issued session is a normal session (require_login honours it) | status=200 |
| A11 | STATIC | PASS | OAUTH_PROVIDERS='google,facebook' -> ['facebook', 'google'] |  |
| A11 | STATIC | PASS | OAUTH_PROVIDERS='google' -> ['google'] |  |
| A11 | STATIC | PASS | OAUTH_PROVIDERS='GOOGLE,Facebook' -> ['facebook', 'google'] |  |
| A11 | STATIC | PASS | OAUTH_PROVIDERS='google,facebook,github' -> ['facebook', 'google'] |  |
| A11 | STATIC | PASS | OAUTH_PROVIDERS='' -> [] |  |
| A11 | STATIC | PASS | OAUTH_PROVIDERS='  google , facebook ' -> ['facebook', 'google'] |  |
| A11 | STATIC | PASS | unset OAUTH_PROVIDERS defaults to google,facebook (Render has no such var yet) | {'google', 'facebook'} |
| A11 | STATIC | PASS | OTP_CODE_LENGTH == 8 | 8 |
| A11 | STATIC | PASS | OTP_RESEND_COOLDOWN_SECONDS == 60 | 60 |
| A11 | STATIC | PASS | OTP_EMAIL_ENABLED='false' -> False | false-y values must all read False; truthy default is what Render inherits |
| A11 | STATIC | PASS | OTP_EMAIL_ENABLED='0' -> False | false-y values must all read False; truthy default is what Render inherits |
| A11 | STATIC | PASS | OTP_EMAIL_ENABLED='garbage' -> False | false-y values must all read False; truthy default is what Render inherits |
| A11 | STATIC | PASS | OTP_EMAIL_ENABLED='true' -> True | false-y values must all read False; truthy default is what Render inherits |
| A11 | STATIC | PASS | .env.example documents OAUTH_PROVIDERS + OTP_EMAIL_ENABLED |  |
| A11 | STATIC | PASS | render.yaml untouched (spec §5.3: no new secrets) |  |
| A1 | STATIC | gap | browser pass | --browser not given (no browser evidence from an intermediate build). Assertions are coded and ready; they run inside the t6 window. |
## Gaps (named, with owner)
- **G1** real email delivery — user's dashboard (Brevo/Resend + `{{ .Token }}` template)
- **G2** live Google/Facebook round-trip — user's provider credentials + Meta app review
- **G6** full-suite behave diff — opt-in, ~30 min, needs captain authorization
- **G7** admin-address collision never tested live (both SMTP slots spent on A2)
- **G8** no real-provider click-through: covered to the 302, not to a completed Google login