# QA BASELINE — t4 (full pytest + auth-hardening behave)

Run by: qa · 2026-09-16 13:50 local · revision `6447d58` (feature/passwordless-otp-social-login)
Working tree at run: tracked code clean (only `docs/dogfood/REPORT.md` modified + untracked prep files).
Method: suites run **sequentially** (shared live Supabase project; STATUS log shows concurrent runs cause transient DNS/DB interference).

## 1. Full pytest — `220 collected → 204 passed, 1 failed, 15 errors` (23.7s)

Command: `.venv/bin/python -m pytest -q`
(Note: `--timeout` unusable — pytest-timeout not installed; async visual script also unrunnable — pytest-playwright not installed.)

### 15 errors — pre-existing environment artifact, NOT regressions
All 15 from `tests/run_comprehensive_visual_test.py`: `fixture 'page' not found` (needs
pytest-playwright, absent from requirements). The file is a standalone Playwright script
that pytest collects; setup-errored for everyone, unrelated to auth. Suggested fix owned by
engineer/captain: add to `collect_ignore` or install the plugin — out of qa scope for t4.

### 1 failure — pre-existing, NOT auth-related
`tests/test_mentor_grounding.py::test_extract_terms_finds_domain_vocabulary` (0.12s, deterministic).
`_extract_terms` (services/mentor_agent.py, untouched since `29ac797`, pre-dating the OTP/OAuth
T-series) returns `['klaviyo','email','automation','specialist','build','abandoned-cart']` — the
test also requires `checkout` and `shopify` in the term set. Pure keyword-extractor/test drift in
the mentor-grounding path; zero intersection with auth/OAuth. Flagged for captain triage.

### Auth surface — ALL GREEN
`tests/test_auth_otp.py + tests/test_config_guards.py + tests/test_csrf.py`: **43 passed** (targeted verbose run).
No OTP, OAuth, config-guard, or CSRF test failed anywhere in the full run either.

## 2. behave auth-hardening — `7/7 scenarios, 34/34 steps PASSED` (7.1s)

Command: `.venv/bin/python -m behave tests/features/auth-hardening.feature`
Covers UAT BUG-1/2/3: wrong password rejected, correct password signs in + `/sprints` 200,
empty password rejected, nonexistent email → generic error (no enumeration leak), empty email →
validation copy, failed admin login leaks no session, `/login` → login redirect.
Matches the historical green marker (`[test] 2026-09-11` auth-hardening 7/7).

## 3. Baseline verdict

**Auth surface is green end-to-end at 6447d58.** The only non-passing pytest items are one
pre-existing mentor-grounding assertion drift and the playwright-plugin collection artifact;
neither is caused by the social-login work, so they are hereby folded into the baseline:

| metric | baseline value |
|---|---|
| pytest pass/fail/error | 204 / 1 (non-auth, pre-existing) / 15 (env artifact) |
| effective auth regressions | **0** |
| behave auth-hardening | 7/7 (34/34 steps) |
| live full behave (reference) | 210 scenarios, 145p/58f/7e (~30m38s), `behave-full-run1.log` |

Future t3 verification should diff against these numbers; "1 failed, 15 errors" is expected
until the two non-auth items above are fixed.
