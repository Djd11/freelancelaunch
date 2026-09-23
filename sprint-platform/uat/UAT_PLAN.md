# UAT PLAN — FreelanceLaunch live deploy
Target: https://freelancelaunch.onrender.com | Creds: admin@sprint-platform.local / admin-pass-123
Rules: NO destructive actions (no deletes, purges, admin data changes). Only permitted write: starting a sprint (idempotent). Real non-headless Chrome (DISPLAY=:0), screenshot every meaningful step → uat/screenshots/. Cold start: request hanging >30s → retry once before failing it.

## Area order (risk-ranked)
1. **auth** — gates everything else
2. **landing** — anonymous first impression
3. **sprint-picker** — core entry to product
4. **sprint-start** — only write op; idempotency (J2 spec)
5. **sprint-dashboard** — main surface
6. **day-flow** — lesson content delivery
7. **proposal-builder** — J6 first-bid challenge
8. **ai-mentor** — J8 Socratic chat
9. **admin** — read-only render check

## Per-area rubric
### 1. auth
Test: GET /login renders; wrong password shows error (no 500, no redirect-as-success); login with seeded creds lands on dashboard (302); logout clears session; authenticated pages redirect to /login when anonymous; CSRF token present in forms.
PASS: all of the above. Blocker: login 500s or seeded creds rejected. Major: wrong-password shows success/state leak. Minor: cosmetic errors on login page.
Screenshots: login page, wrong-password error, post-login dashboard, logged-out state.

### 2. landing
Test: anonymous GET / — title, hero, CTAs; every nav link resolves (click each, back); footer links; no broken images; pricing/preview sections if present; response <10s warm.
PASS: all links resolve, no 5xx, no unstyled/JS-error blank sections. Blocker: 5xx on /. Major: any dead link or CTA. Minor: typos, alignment, console warnings.
Screenshots: hero, each CTA target page, footer.

### 3. sprint-picker
Test: authenticated picker lists clusters with active postings (≥1); each cluster card link works; empty-state renders if no postings (no blank page); "request a sprint" path if present.
PASS: clusters render with counts; links resolve. Blocker: picker 5xx/blank. Major: postings count 0 or wrong, cards broken. Minor: layout.
Screenshots: picker page, one cluster detail.

### 4. sprint-start (ONLY permitted write)
Test: start sprint for a cluster → 302 to dashboard/sprint; START AGAIN → still 302 to the SAME sprint, no duplicate sprint rows, no 500 (idempotency — eng-spec J2); direct revisit shows existing sprint.
PASS: double-start idempotent (same redirect target both times). Blocker: 500 or duplicate sprint. Major: redirects to different sprint on second start. Minor: UX (no feedback).
Screenshots: picker before, first start redirect target, second start redirect target (same URL).

### 5. sprint-dashboard
Test: dashboard renders current sprint: day cards, progress, gate state; nav to day; no dead links; empty sprint state renders if applicable.
PASS: all elements render with real data. Blocker: 5xx/blank. Major: wrong progress, dead day links. Minor: layout.
Screenshots: dashboard, day card detail.

### 6. day-flow
Test: open day 1: lesson content renders (title, body, check items); complete/check an item if it's a safe UI action (if it mutates real progress, SKIP and note as untested-destructive); next-day navigation.
PASS: content renders, nav works. Blocker: 5xx/empty lesson. Major: check items broken. Minor: formatting.
Screenshots: day page, lesson content.

### 7. proposal-builder
Test: renders drafts (generate is allowed — LLM write to user's own proposals); challenge/first-bid flow renders; form fields present; submit path is human-initiated — test render + validation only, do NOT actually submit to external platforms.
PASS: builder renders, drafts visible, validation errors on empty input. Blocker: 5xx. Major: forms broken. Minor: copy.
Screenshots: builder page, validation error state.

### 8. ai-mentor
Test: mentor chat page renders; send a short test question; response arrives (LLM latency ok, may take 30-60s); grounding — answer references the sprint/job context.
PASS: question → grounded answer round-trip. Blocker: 5xx or no response. Major: response not job-grounded. Minor: formatting.
Screenshots: mentor page, sent question, response.

### 9. admin (READ-ONLY)
Test: GET each admin page: dashboards, users list, platforms, cohorts — renders without 5xx; links work; NO clicks on any delete/purge/destructive button; verify destructive buttons exist but are NOT exercised.
PASS: all admin pages render. Blocker: 5xx on admin. Major: pages render but links broken. Minor: layout.
Screenshots: each admin page.

## Exit criteria
All 9 areas have reports in uat/reports/<area>.md + STATUS.md lines. Then verifier independently re-checks a sample of PASS claims, counts reports vs plan (9/9), writes uat/FINAL_VERDICT.md (PASS/FAIL + evidence).
