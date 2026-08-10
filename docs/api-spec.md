# FreelanceLaunch — HTTP API Specification

**Status:** Active · **Version:** 1.0 · **Date:** 2026-08-10 · **Branch:** `sprint-track`
**Coverage:** all route blueprints registered in `app.py` (v1 + Sprint Track v2).
**Companion:** BDD contract tests in [`tests/features/api-contract.feature`](../tests/features/api-contract.feature) and steps in [`tests/steps/test_api_contract.py`](../tests/steps/test_api_contract.py).

> This is the **source of truth for the HTTP surface**. Endpoints are grouped by blueprint.
> Auth convention: page routes (`GET` that render HTML) redirect unauthenticated users to `/auth/login`; JSON API routes return `401 {"error": "Not logged in"}`.

---

## 1. Conventions

- **Base path:** Flask app served at `RENDER_EXTERNAL_URL` (default `http://localhost:5000`).
- **Auth:** cookie session keyed by `session["user_id"]` → `user_profiles` lookup via `before_request`.
- **JSON:** request bodies use `application/json` unless a form is noted.
- **Error shape:** JSON APIs return `{"error": "<message>"}` with an appropriate status code.
- **Data layer:** every handler delegates to Supabase via the `get_supabase()` service-role client.

### Status codes used
| Code | Meaning |
|------|---------|
| `200` | Success (JSON or rendered HTML) |
| `302` | Redirect (auth gate / post-submit) |
| `400` | Invalid request body / missing field / bad enum |
| `401` | Not logged in (JSON APIs) |
| `500` | Internal error (rare; no-500 philosophy keeps this minimal) |

---

## 2. Auth (`/auth`)

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| GET/POST | `/auth/signup` | — | form: email, password, display_name | 302 → login/dashboard |
| GET/POST | `/auth/login` | — | form: email, password | 302 → dashboard |
| GET | `/auth/logout` | ✓ | — | 302 → index |
| GET/POST | `/auth/profile` | ✓ | form: display_name | 302 → profile |

---

## 3. Topics (`/topics`)

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| GET | `/topics` | — | — | HTML topic explorer |
| GET | `/topics/<slug>` | — | path: slug | HTML topic detail w/ demand data |
| POST | `/topics/<slug>/enroll` | ✓ | form: slug | 302 → dashboard |

---

## 4. Enroll / custom topic (`/enroll`)

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| POST | `/enroll/new` | ✓ (401) | JSON `{ "topic": "<name>" }` | 200 `{status, topic, redirect}` / 400 short / 401 |

**Contract notes**
- `topic` trimmed, must be ≥ 3 chars → else `400 {"error":"Topic name must be at least 3 characters"}`.
- On success: creates/upserts `topics` row, resolves slug→UUID, finds-or-creates cohort, kicks async curriculum generation, updates `user_profiles`, creates `freelance_pipeline` row.
- Response: `200 {"status":"enrolled","topic":"<name>","redirect":"/platforms/setup"}`.

---

## 5. Dashboard (`/dashboard`)

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| GET | `/dashboard/` | ✓ | — | HTML dashboard |
| GET | `/dashboard/day/<int:day_number>` | ✓ | path: day_number | HTML day view |

---

## 6. Progress (`/api/progress`)

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| POST | `/api/progress/mark` | ✓ (401) | JSON `{cohort_video_id, field, day_number?}` | 200 `{success, message, day_complete}` / 400 / 401 |
| POST | `/api/progress/rate` | ✓ (401) | JSON `{cohort_video_id, rating}` | 200 `{success}` / 400 / 401 |

**Contract notes — `/mark`**
- `field` must be one of `video_watched | practice_completed | apply_completed`; missing `cohort_video_id` or bad `field` → `400 {"error":"Invalid request"}`.
- Creates or updates a `user_progress` row. When all three sections are done → sets `freelance_pipeline.stage='applying'`.
- Success: `200 {"success":true,"message":"<nudge>","day_complete":<bool>}`.

**Contract notes — `/rate`**
- `rating` must be integer 1–5; missing `cohort_video_id` or out-of-range → `400 {"error":"Invalid request"}`.
- Upserts `user_progress.self_rating`. Success: `200 {"success":true}`.

---

## 7. Curriculum generation API (`/api`)

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| POST | `/api/generate-curriculum/<slug>` | ✓ | path: slug | 200 `{status, ...}` / 401 |
| GET | `/api/generation-status/<slug>` | ✓ | path: slug | 200 progress JSON |
| GET | `/api/generation-log/<slug>` | ✓ | path: slug | 200 `{entries: [...]}` |
| POST | `/api/regenerate-day/<slug>/<int:day_number>` | ✓ (admin) | path: slug, day_number | 200 JSON |

**Contract notes**
- Generation is **async**; progress + per-day log lines persist to `curriculum_generation_log` (DB-backed) so polling survives across gunicorn workers.
- `/generation-status/<slug>` returns the in-memory fast-path dict (falls back to DB).
- `/generation-log/<slug>` returns the structured log entries.

---

## 8. Search (`/search`)

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| GET | `/search/api` | — | query `q` (≥2 chars) | 200 `{query, curated_matches, platform_results, curated_count}` |
| GET | `/search/suggestions` | — | — | 200 `[ {name, slug, jobs, rate}, ... ]` |
| GET | `/search/curriculum/<slug>` | — | path: slug | 200 `{days, count}` |

**Contract notes — `/search/api`**
- `q` missing or < 2 chars → `200 {"error":"Query too short","results":[]}`.
- Platform data resolution order: fresh `topic_intelligence` cache → live Playwright scrape → stale cache → heuristic (flagged `data_source: "synthetic"`).
- Each platform result: `{status, jobs, avg_rate, url, source}`.

---

## 9. Platform verification (`/platforms`)

All `/platforms/api/*` require auth → `401` when not logged in.

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| GET | `/platforms/setup` | ✓ | — | HTML setup |
| POST | `/platforms/api/select` | ✓ | JSON `{platform}` | 200 `{status, platform, signup_url?}` / 400 |
| POST | `/platforms/api/verify` | ✓ | JSON `{platform}` | 200 `{status:"verified", platform}` / 400 |
| POST | `/platforms/api/skip` | ✓ | JSON `{platform}` | 200 `{status:"skipped", platform}` |
| POST | `/platforms/api/remove` | ✓ | JSON `{platform}` | 200 `{status:"removed", platform}` |
| GET | `/platforms/api/status` | ✓ | — | 200 `{platforms, has_verified, pending_count, needs_setup}` |

**Contract notes**
- Valid platforms: `upwork`, `fiverr`, `contra`. Unknown platform on select/verify → `400 {"error":"Invalid platform: <p>"}`.
- `/api/select` returns `status:"already_exists"` when the link already exists, else `"created"` with `signup_url`.
- `/api/status` computes `has_verified` (any verified), `pending_count`, `needs_setup` (zero links).

---

## 10. Freelance / Funnel 2 (`/freelance`)

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| GET | `/freelance/pipeline` | ✓ | — | HTML pipeline |
| POST | `/freelance/api/update` | ✓ (401) | JSON `{field, value}` | 200 `{success}` / 400 / 401 |
| POST | `/freelance/contract/add` | ✓ | form fields | 302 → pipeline |

**Contract notes — `/api/update`**
- `field` must be one of: `stage | proposals_sent | responses_received | interviews_held | offers_received | contracts_won | is_actively_seeking`.
- Unknown field → `400 {"error":"Invalid field: <f>"}`.
- `stage == "applying"` also sets `started_learning_at`. Success: `200 {"success":true}`.

---

## 11. Payments (`/payments`)

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| GET | `/payments/pricing` | — | — | HTML pricing |
| POST | `/payments/create-checkout` | ✓ | form: tier | 302 → Stripe Checkout or Gumroad |
| GET | `/payments/success` | — | query: session_id | 302 → dashboard |

---

## 12. Admin (`/admin`) — `ADMIN_EMAIL` gate

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| GET | `/admin/` | admin | — | HTML overview |
| GET | `/admin/users` | admin | — | HTML user list |
| GET | `/admin/production` | admin | — | HTML production log |
| POST | `/admin/production/trigger/<video_id>` | admin | path: video_id | 302 → production |

---

## 13. Preview (`/preview`)

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| GET | `/preview/day/<int:day_number>` | — | path: day_number | HTML TwoPanel preview + TTS |

---

## 14. Deliverables (`/deliverables`)

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| GET/POST | `/deliverables/submit` | ✓ | form | HTML/302 |
| GET | `/deliverables/portfolio` | ✓ | — | HTML |

---

## 15. System

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| GET | `/health` | — | — | 200 `{status:"ok", env_set:<bool>}` |
| GET | `/` | — | — | landing (redirects to dashboard when logged in) |

---

## 16. Sprint Track (`/sprints`) — v2

The Sprint Track is the parallel placement path. All endpoints are additive to v1.

### 16.1 Sprint lifecycle

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| POST | `/sprints/new` | ✓ (302→login) | form `topic` | 302 → sprint dashboard |
| GET | `/sprints/<sprint_id>` | ✓ (302→login) | path: sprint_id | HTML sprint dashboard + meter |
| GET | `/sprints/<sprint_id>/day/<int:day_no>` | ✓ | path | HTML day view |
| POST | `/sprints/<sprint_id>/day/<int:day_no>/complete` | ✓ (401) | path | 200 `{ok, day_no, next_day, meter}` |

**Contract notes — `/sprints/new`**
- `topic` defaults to `email-automation`; lowercased + stripped.
- Resolves/creates a `job_clusters` row; seeds a demo `job_feed` when the cluster is empty.
- Creates the `sprints` row (phase A, day 1), builds the 14-day plan (`sprint_planner.build_plan`), and recomputes the unlock meter.
- On success flashes a message and **302 redirects** to the sprint dashboard.

**Contract notes — `/complete` (the motivational moment)**
- Marks the `sprint_days` row done, advances `sprints.current_day` + `phase`, recomputes the meter via `unlock_engine.recompute`.
- Response: `200 {"ok":true,"day_no":<n>,"next_day":<n+1>,"meter":{completed_days,unlocked,total,newly_unlocked}}`.

### 16.2 Mock contract (Phase B)

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| GET | `/sprints/<id>/contract` | ✓ | — | HTML contract view |
| POST | `/sprints/<id>/contract/submit` | ✓ | form `submission_url` | 302 → contract view |

### 16.3 Proposals (Phase C)

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| GET | `/sprints/<id>/proposals` | ✓ | — | HTML proposals |
| POST | `/sprints/<id>/proposals/<proposal_id>/submit` | ✓ | path | 302 → proposals |

### 16.4 Badge

| Method | Path | Auth | Body/Query | Response |
|--------|------|------|-----------|----------|
| GET | `/sprints/<id>/badge` | ✓ | — | HTML badge page |

---

## 17. Data layer (Supabase tables touched by the APIs)

| Table | Purpose |
|-------|---------|
| `user_profiles` | current user; `avatar_url` stores the email (legacy) |
| `topics` / `curricula` / `curriculum_days` | v1 curriculum |
| `cohorts` / `cohort_videos` | v1 cohorts |
| `user_progress` | per-day completion + self-rating |
| `user_platforms` | Upwork/Fiverr/Contra links + status |
| `freelance_pipeline` / `contracts` | Funnel 2 |
| `curriculum_generation_log` | async gen progress/log |
| `job_clusters` / `job_feed` | Sprint Track demand source of truth |
| `sprints` / `sprint_days` | Sprint Track plan + progress |
| `sprint_unlock_snapshots` | O(1) meter reads |
| `capstone_briefs` / `verification_reviews` | Phase B gate |
| `proposals` | Phase C drafts + submissions |
| `badges` | demand-validated badges |

---

## 18. Versioning & contract stability

- The `sprints` blueprint is **additive**; it does not modify v1 routes.
- Sprint endpoint responses are JSON for state-changing calls (`/complete`) so the meter can update without a full page reload.
- Any change to a JSON request/response shape MUST update this spec AND the BDD contract tests in `tests/features/api-contract.feature`.
