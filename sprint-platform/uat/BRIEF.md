# UAT BRIEF — sprint-platform (FreelanceLaunch live deploy)

Target: https://freelancelaunch.onrender.com  (LIVE production, Render free tier — expect ~50s cold starts)
Admin creds: admin@sprint-platform.local / admin-pass-123
Workspace: ~/Documents/exp_money/daily_learning_freelance/sprint-platform/uat/ (this directory)

## Team assignments
- architect: write UAT_PLAN.md (test areas, per-area pass criteria, order). Append progress to STATUS.md.
- tester: execute UAT_PLAN.md area by area. Write one report per area to reports/<area>.md, screenshots to screenshots/. Append progress to STATUS.md after EVERY area.
- verifier: after tester finishes, independently re-check a sample of PASS claims against the live site, count reports vs plan, write FINAL_VERDICT.md.

## Conventions (ALL bots)
- Append one line to STATUS.md at each step: `[<bot>] <timestamp> <what you're doing/done>`.
- Reports are evidence-first: every claim backed by a screenshot path or HTTP status.
- Bug format: page, element, expected vs actual, steps to reproduce, severity (blocker/major/minor), screenshot.
- Browser: real non-headless Chrome, DISPLAY=:0. Screenshot every meaningful step.
- Render cold start: if a request hangs >30s, retry once before calling it a failure.

## Scope (from tests/features/*.feature — primary user journeys)
1. landing — anonymous landing page, all CTAs/links
2. auth — login with admin creds, wrong password, logout
3. sprint-picker — job cluster picker, active postings visible
4. sprint-start — start sprint for a cluster; idempotency (double-start never duplicates/500s) — the ONLY write operation allowed in UAT
5. sprint-dashboard — dashboard renders, day/lesson cards, progress
6. day-flow — open a day/lesson, content renders
7. proposal-builder — proposal builder flow renders and functions
8. ai-mentor — mentor chat renders, responds
9. admin — admin pages render (READ-ONLY: no deletes, no purges, no user management changes)

## Hard rules
- NO destructive actions anywhere (no delete buttons, no purge scripts, no admin data changes).
- The only permitted write: starting a sprint (idempotent by design) and normal UI navigation.
- If login fails with the seeded creds, that is itself a blocker-severity bug — report it, don't guess other creds.
