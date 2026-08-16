# CTA Coverage Gap — Fix Plan (2026-16-08)

Audit: every `<a>/<button>/<form>` in `templates/` was diffed against every scenario in
`tests/features/`. ui-ux.feature is green by construction — it only asserts what it covers.
This plan closes the gaps found.

## Gap → fix matrix

| # | Gap | Class | Fix | Verified by |
|---|-----|-------|-----|-------------|
| 1 | Contract "Mark complete" CTA (sprint_dashboard.html:143 → POST /sprints/<id>/contract/<cid>/complete) — zero coverage | missing scenario | ui-ux.feature: add contract → dashboard shows "Mark complete" → POST complete → `contracts_completed == 1`. New steps: mark-most-recent-contract-complete, contracts_completed assertion | behave |
| 2 | Admin create form pages (GET /admin/{clusters,feed,cohorts}/create) never opened — admin.feature only POSTs JSON | missing scenario | admin.feature: GET all 3 form pages, assert 200 + form heading | behave |
| 3 | Form-encoded POST path untested everywhere (browser forms ≠ JSON; Flask 415 class) | missing scenario | admin.feature: submit all 3 admin creates as form data → 302 + row exists + tracked for cleanup. New steps: POST-with-form-data, row-tracked | behave |
| 4 | Mentor chat: browser form path (form-encoded, JS-intercepted) untested; only JSON POST covered | missing scenario | ui-ux.feature: POST /mentor/turn form-encoded → 200 + answer. JS intercept itself → visual run | behave + visual |
| 5 | Demand refresh: API covered, but NO UI CTA exists anywhere | product gap | templates/admin/clusters.html: per-row "Refresh demand" form button; admin.feature scenario on a scoped throwaway cluster (never touches email-automation static counters/snapshots — same isolation as api.feature's refresh scenario) | behave |
| 6 | Copy proposal button — JS-only, attribute-presence only | harness ceiling | visual_journey.py: click `[data-copy-proposal]`, wait for "Copied ✓" | visual run |
| 7 | Mentor Send — JS intercept (fetch + reload) never exercised | harness ceiling | visual_journey.py: fill form, click Send, wait for the question to render from history replay | visual run |
| 8 | Lesson player + generation-poll JS — never exercised | harness ceiling | visual_journey.py: assert lesson block renders on day view; let gen poll fire on dashboard; console-error budget asserted = 0 at end | visual run |

## Out of scope (noted, not fixed)

- Low-risk nav/anchor links already covered transitively (landing `#how`, login back-link, admin base nav).
- `/sprints/<id>/badge` and `/dashboard/` are covered (mock-contract.feature, api.feature).

## Exit criteria

1. Full behave suite: 0 failed / 0 errors.
2. Second run of touched features: zero row growth (idempotency probe).
3. Visual run: all new checks pass, console errors = 0, DB left as found.

## Files touched

- tests/features/ui-ux.feature, tests/features/admin.feature (+ docs/bdd copies)
- tests/steps/common_steps.py (form-data POST step)
- tests/steps/action_steps.py (contract-complete, contracts_completed, row-tracked, refresh-CTA steps)
- templates/admin/clusters.html (Refresh demand button)
- scripts/visual_journey.py (copy/mentor/lesson/gen checks, headless env override, console assert, mentor-session cleanup)
