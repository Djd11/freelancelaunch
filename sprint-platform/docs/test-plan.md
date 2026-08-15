# Sprint Platform — E2E Test Plan (BBT → BDD)

**Date:** 2026-08-15 · **Branch:** `sprint-platform` · **Mode:** LIVE Supabase (dedicated test project)
**Method:** Behavior-driven testing (behave) first; any failure → behavior-driven development fix (harness or app), then re-run green. Visual headed-browser pass at the end.

---

## 1. Baseline (run 2026-08-15)

```
5 features passed, 3 failed, 1 error
57 scenarios passed, 7 failed, 1 error
447 steps passed, 7 failed, 1 error, 8 skipped
```

| # | Scenario | Symptom | Root cause | Class |
|---|----------|---------|------------|-------|
| 1 | ai-mentor: "mentor page renders a chat with context chip" | ERROR 42P10 | `capstone_briefs` seeded with `on_conflict="sprint_id"` but the table has **no unique constraint on sprint_id** | harness |
| 2 | ai-mentor: "mentor turn grounded in terminology" | answer missing 'cart summary' | Brief never seeded (cause 1) → mentor falls back to first job_feed row by id → picks a **leaked duplicate** "New Klaviyo Flow" row instead of the mapped job | harness + pollution |
| 3 | ai-mentor: "mentor sessions scoped to sprint and job" | no session for (s1, job-1) | Same wrong-job fallback as #2 | harness + pollution |
| 4 | day-flow: "missing sprint redirects" | got 200, expected 302 | `SprintIDRewritingClient` calls `resolve_sprint_id("does-not-exist")` which **creates** a sprint for the unknown id | harness |
| 5 | demand-profile: "badge shows live counter and trend" | missing '450 active jobs right now' | Slug `/profile/maya` resolves to the **first** "Maya Chen" profile in the table; a second Maya (persona user `profile-maya-chen`, is_public=False, no badge) was created by the freelancer-filter scenario and leaks across runs | harness + feature-persona bug |
| 6 | demand-profile: "badge shows provenance" | missing 'Mock contract verified' | Same as #5 | same |
| 7 | demand-profile: "portfolio shows case studies" | missing case-study title | Same as #5 | same |
| 8 | proposal-builder: "First-Bid tracks progress out of 5" | proposals_sent=6, expected 1 | Sprint row **reused across scenarios** (resolve finds existing user+cluster sprint); a prior scenario left `proposals_sent=5`; `seed_sprint` never resets outcome counters; reused sprints are never cleaned | harness isolation |

**Underlying systemic issue:** the live-DB harness is not idempotent/isolated:
- `environment._seed_static_data` generates fresh `uuid4` job_feed + cohort rows **every run** (upsert-on-id never matches) → ~300 duplicate job_feed rows, duplicate cohorts accumulated.
- `resolve_sprint_id` reuses any existing sprint for (user, cluster) and never tracks it for cleanup → state leaks between scenarios and between runs.
- Persona steps (`freelancer "Maya Chen"`) create **new auth users** with colliding display names instead of mapping to the canonical demo/other users.
- Admin create-scenarios insert rows never cleaned (`test-cluster`, "New Klaviyo Flow", "Cohort #13", browser-test rows).
- `step_no_passing` performs a **global** wipe of badges/reviews (unsafe even in a dedicated project).

## 2. Fixes (harness — must land before trusting any result)

1. **Deterministic static IDs**: job_feed + cohort static seeds use `uuid5(NAMESPACE, fake_id)` so upserts are idempotent; demand snapshot delete-then-insert.
2. **No-create URL rewriting**: `SprintIDRewritingClient` resolves sprint ids with `resolve_only=True` (unknown fake id → passed through unchanged → route 302s as specced).
3. **Per-scenario sprint isolation**: `resolve_sprint_id` tracks every sprint it returns (created *or* reused); `seed_sprint` resets all outcome counters; cleanup deletes tracked sprints (FK cascade cleans days/snapshots/briefs/proposals/reviews).
4. **Persona mapping**: `freelancer "Maya Chen"` → demo user, `"Jordan Lee"` → other user (matches feature intent: the logged-in user IS Maya). No more duplicate auth users.
5. **capstone briefs**: delete-then-insert (no bogus on_conflict).
6. **Admin create cleanup**: 201 JSON creates are tracked (path→table) and deleted in `after_scenario`.
7. **Scoped wipes**: `step_no_passing` limited to the test user's rows.
8. **One-time pollution cleanup** of the live test project (leaked feed rows, cohorts, duplicate personas, stale sprints, test clusters).

## 3. Coverage gaps vs engineering spec → new BDD scenarios

| Gap (eng-spec ref) | New scenario |
|---|---|
| No end-to-end journey exists (J1→J7 chained) — the core ask | `full-journey.feature`: landing → picker → start sprint → day completes 1–5 (meter upticks) → copy-work → gate A pass → Phase B unlocks → contract brief → deliverable submit → gate B pass → Phase C unlocks → first proposal submitted → sprint completed → badge issued → public profile shows provenance → client filter returns the freelancer |
| Login flow never exercised over HTTP (features inject the session) | `landing.feature`: POST /auth/login with email → redirect /sprints → session works |
| Cohort line unasserted (J3: "Cohort #12 · ends Aug 23") | `sprint-dashboard.feature`: dashboard contains "Cohort #12" |
| Admin→learner handoff untested (admin curates feed, learner sees it — the admin feature's stated purpose) | `admin.feature`: admin-created active cluster appears on `/sprints` picker |

## 4. App bugs to watch (BDD-fix if red)

- `profile._resolve_user` first-match slug resolution is non-deterministic with same-name users → make deterministic (exact match > prefix; stable order).
- `mentor._context` fallback picks first job by id → fine once feed is clean, but should prefer `unlock_day` order for determinism.
- `routes/auth.login` accepts ANY email and falls back to logging in as demo user — ~~acceptable for demo mode, flag for hardening~~ **RESOLVED 2026-08-15**: the demo fallback and the entire in-memory FakeSupabase dev mode were removed; login now refuses unknown emails (see execution log entry below).

## 5. UI/UX audit (claude-design skill, 10-tell slop diagnostic)

Current score **7/10** — tells fired: 1 (blue→violet gradient everywhere), 2 (generic indigo/violet hue), 3 (equal-weight 3-card phase grid), 4 (colored border-left accent rails on cards), 6 (gradient monument stats), 7 (emoji icon toppers on every heading), 9 (default system-ui type), 10 (admin screens are unstyled `<table border=1>` — wrong surface entirely).

**Redesign commitment (per surface):**
- Landing = **Decide/Learn** (hero correct) · Picker = **Explore** · Dashboard = **Monitor** · Day = **Operate/Learn** · Contract & Proposals = **Operate** · Profile = **Decide** · Mentor = **Command/Inspect** · Admin = **Operate**.
- Design system: warm editorial (Anthropic-marketplace style) — cream `#FAF9F5` canvas, ink `#1A1917`, terracotta accent `#C96442`, serif display (Fraunces→Georgia fallback) + sans body, hairline borders instead of shadow-heavy cards, no gradients, no accent rails, real focus states, `prefers-reduced-motion` respected, ≥44px hit targets.
- All BDD-asserted copy preserved verbatim (lock strings, "Job Unlock Meter", "First-Bid", "Mock contract verified", "450 active jobs right now", "TwoPanel", 🏅 badge glyph, etc.).
- Admin gets real templates on the shared design system.

## 6. Visual verification

Headed Playwright run (DISPLAY=:0, visible browser, video + screenshots):
admin login → dashboard → clusters → feed → cohorts → create flows; then learner journey: login → picker → start → dashboard → day → contract → proposals → profile → mentor. Every screen captured.

## 7. Exit criteria

- behave: 0 failed, 0 errors, all features green (including new journey scenarios).
- Visual pass: every screen renders the redesigned UI with no console errors.
- Live test project left clean (idempotent re-runs produce no growth).

## 8. Execution log (2026-08-15)

- **Run 2** (post-harness-fix): 64 passed, 0 failed, 1 error — day-flow "missing sprint redirects" crashed with Postgres 22P02 (`load_sprint` passed a non-UUID straight to a uuid column).
- **Fix**: `routes/__init__.py` — `_is_uuid()` guard in `load_sprint`/`load_cohort`; malformed ids now short-circuit to None → specced 302. Same class of bug closed for every downstream uuid-column query (all sit behind `load_sprint`).
- **Run 3**: 9 features, 65 scenarios, 463 steps — **all green**.
- **Gap scenarios added** (run 4): `full-journey.feature` (landing→picker→start→days 1–5→copy-work→gate A→contract→gate B→first proposal→completed→badge→profile provenance→client filter, all over real HTTP), `landing.feature` login-over-HTTP, `sprint-dashboard.feature` cohort line ("Cohort #12 · ends 2026-08-23"), `admin.feature` admin→learner handoff (admin-created active cluster appears on `/sprints`). New steps in `tests/steps/journey_steps.py` + login-form step in `action_steps.py`.
- **Harness idempotency fix**: `step_cluster_postings` no longer zeroes a pre-existing static cluster's demand numbers (was clobbering email-automation job_count to 0).
- **Run 4**: 10 features, 69 scenarios, 535 steps — **all green**.
- **Templates**: login/clients/pricing redesigned on the warm-editorial design system; admin got real templates (`templates/admin/*` — base, dashboard, clusters, feed, cohorts + 3 forms) and `routes/admin.py` renders them (no more inline `<table border=1>` HTML). All BDD-asserted copy preserved verbatim.
- **Visual run**: `scripts/visual_journey.py` — headed Chromium on DISPLAY=:0, video + 21 screenshots, admin leg + full learner journey, cleans up its sprint/cluster afterwards.
- **Visual run caught 2 real app bugs** (BDD never hit them — it only POSTs JSON / injects sessions):
  1. Flask 3.1 `request.get_json()` raises 415 on form-encoded POSTs → all three admin create routes now use `get_json(silent=True) or request.form.to_dict()`.
  2. Demo user's `user_platforms` rows were deleted by per-scenario cleanup and never restored (proposal submission silently rejected) → `environment._seed_static_data` now re-upserts upwork/fiverr every run; the visual script also ensures them itself.
- **Visual run result**: 21/21 screenshots + full-journey video, 0 console errors after favicon fix (inline data-URI icon in base.html). Screenshots in /tmp/visual_run/shots/, video in /tmp/visual_run/videos/.
- **Auth 22P02 fix** (reported on live server: `/sprints/email-automation/start` crashed with `invalid input syntax for type uuid: "demo-user"`): `routes/auth.py` fell back to the literal `"demo-user"` session id when no email matched — valid in FakeSupabase dev mode, fatal against live Postgres uuid FKs. Now: live mode refuses unknown emails (flash + re-render, no session); dev mode keeps one-click demo login. `app.load_user` additionally drops any non-UUID session id in live mode so stale dev cookies can't reach a uuid write. Verified over HTTP against the live project (login → start → dashboard, stale-cookie drop) and full suite re-run.
- **Fake/dev-mode removal** (2026-08-15): the entire in-memory FakeSupabase stack was deleted — `services/fake_supabase.py`, `services/seed_demo.py`, `get_dev_db`/`reset_dev_db`/`is_live_configured` in `services/supabase_client.py`, the `DEMO_USER_ID` login fallback in `routes/auth.py`, the FakeSupabase admin branch in `routes/admin.py`, the dev-fake `/health` branch and demo seeding in `app.py`/`run.py`, the hardcoded `FALLBACK_FEATURED` demand numbers in `routes/main.py`, and the "Demo mode" copy in `templates/login.html`. The app now has exactly one data layer: the live Supabase project (missing config → loud RuntimeError, never a silent empty store). All 18 feature files + the step definition moved from "in-memory test database" to "live test database"; the harness's `fake_*` identifiers were renamed to `fixture_*`; `seed_live.py` was rewritten to seed only persistent reference rows with deterministic uuid5 IDs (it previously inserted string ids into uuid columns and seeded a persistent demo sprint that polluted harness isolation). Post-removal verification: full suite green twice (69 scenarios / 535 steps each), second run produced zero row growth (idempotency proof), `/health` live.
