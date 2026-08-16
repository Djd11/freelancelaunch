# FreelanceLaunch · Sprint Platform — API Reference (v1)

**Status:** Synced to the implemented codebase · **Date:** 2026-08-16 · **Branch:** `sprint-platform`
**Source of truth:** the Flask blueprints in `routes/` (mirror `architecture.md` §4.2).
**Companions:** [`engineering-spec.md`](./engineering-spec.md) · [`architecture.md`](./architecture.md) · [`bdd/`](./bdd/)

---

## 1. Conventions

- **Server-rendered app.** Almost every route returns a Jinja2 page. The JSON endpoints
  are listed explicitly in §3 — everything else is HTML.
- **Auth** is a session cookie (`session["user_id"]`) that **must reference a real
  `auth.users` UUID**. `routes/__init__.py` drops malformed ids before they can reach a
  Postgres uuid FK (22P02). `require_login()` redirects anonymous users to
  `GET /auth/login`. See [`auth.py`](../routes/auth.py) and [`app.py`](../app.py).
- **Ownership:** every `/sprints/<id>` state change verifies `sprint.user_id == g.user.id`;
  foreign sprints redirect to `/dashboard/` (or `404 {"error": ...}` on JSON routes).
- **Side effects are POST-only.** A GET must never write (`POST /sprints/<cluster>/start`
  is enforced in the route's method list).
- **Malformed ids never 500.** Non-UUID sprint ids short-circuit to the not-found redirect.
- **Admin:** all `/admin/*` routes require `role=admin` auth metadata (or the
  `ADMIN_USER_ID` test config). JSON requests get `403 {"error": "Admin access required"}`.
- **No-500 philosophy:** LLM-backed endpoints degrade to deterministic fallbacks; DB errors
  on background work are logged, never surfaced to the request.

---

## 2. Endpoint index

| Method | Path | Blueprint | Auth | Purpose |
|--------|------|-----------|------|---------|
| GET | `/health` | app | public | Liveness + Supabase reachability |
| GET | `/` | main | public | Landing (demand counter card) |
| GET | `/topics` | main | public | Topics nav → redirects to `/sprints` |
| GET | `/sprints` | main | login | Sprint picker (demand-validated list) |
| POST | `/sprints/request` | main | login | Request-a-sprint intake (creates `requested` cluster) |
| POST | `/sprints/<cluster_key>/start` | main | login | **Enroll**: sprint + cohort + plan skeleton + async content |
| GET | `/pricing` | main | public | Pricing page |
| GET | `/dashboard/` | main | login | Redirect to `/sprints` |
| GET | `/sprints/<sprint_id>` | sprints | owner | Sprint dashboard (meter, phases, momentum, contracts) |
| GET | `/sprints/<sprint_id>/day/<int:day_no>` | sprints | owner | Day view (lesson + copy-work anatomy) |
| GET | `/sprints/<sprint_id>/generation` | sprints | owner | **JSON** content-generation progress |
| POST | `/sprints/<sprint_id>/day/<int:day_no>/complete` | sprints | owner | **JSON** complete a day → meter uptick + momentum |
| POST | `/sprints/<sprint_id>/day/<int:day_no>/copywork` | sprints | owner | Submit copy-work rubric → Gate A auto-check |
| POST | `/sprints/<sprint_id>/complete` | sprints | owner | Explicitly complete the sprint |
| GET | `/sprints/<sprint_id>/badge` | sprints | owner | Issue the Demand-Validated badge (idempotent) |
| GET | `/sprints/<sprint_id>/contract` | contract | owner | Mock Contract brief + case-study form |
| POST | `/sprints/<sprint_id>/contract/submit` | contract | owner | Submit deliverable → Gate B auto-check |
| POST | `/sprints/<sprint_id>/contract/add` | contract | owner | Record a won contract → earnings roll-up |
| POST | `/sprints/<sprint_id>/contract/<contract_id>/complete` | contract | owner | Mark a contract completed |
| POST | `/sprints/<sprint_id>/case-study` | contract | owner | Upsert the Problem/Solution/Result case study |
| GET | `/sprints/<sprint_id>/proposals` | proposals | owner | First-Bid challenge + iteration diagnosis |
| POST | `/sprints/<sprint_id>/proposals/<proposal_id>/submit` | proposals | owner | Human-initiated submission (+1 `proposals_sent`) |
| POST | `/sprints/<sprint_id>/proposals/<proposal_id>/respond` | proposals | owner | Log response/interview/offer outcome |
| GET | `/profile/<slug>` | profile | public | Public demand profile (badges + case studies) |
| GET | `/profile/me` | profile | login | Redirect to own public profile |
| GET | `/mentor` | mentor | login | AI mentor chat page |
| POST | `/mentor/turn` | mentor | login | **JSON** mentor answer (Socratic, grounded) |
| GET | `/clients/freelancers` | clients | public | Badge-filtered freelancer search |
| GET | `/auth/login` · POST | auth | public | Login form / establish session |
| GET | `/auth/logout` | auth | public | Clear session → `/` |
| GET | `/admin/` | admin | admin | Admin dashboard |
| GET | `/admin/clusters` · `POST /admin/clusters/create` | admin | admin | List / upsert clusters |
| GET | `/admin/feed` · `POST /admin/feed/create` | admin | admin | List / insert feed postings |
| GET | `/admin/cohorts` · `POST /admin/cohorts/create` | admin | admin | List / create cohorts |
| POST | `/admin/clusters/<cluster_key>/refresh` | admin | admin | **JSON** recompute live counters + snapshot |

---

## 3. JSON endpoints

### `GET /health`
Public liveness probe. Pings `job_clusters` to prove RLS + schema are reachable.

```json
200 {"status": "ok", "mode": "supabase", "tables": "live",
     "project": "<project-ref>", "clusters_reachable": true, "sample_count": 3}
503 {"status": "error", "mode": "supabase", "tables": "live",
     "project": "<project-ref>", "clusters_reachable": false, "error": "..."}
```

### `GET /sprints/<sprint_id>/generation`
DB-backed content-generation progress (eng-spec §5). The count of `sprint_days`
whose `action_payload.lesson` is populated IS the log; polled by the dashboard spinner.

```json
200 {"status": "generating", "generated": 7, "total": 14}
200 {"status": "ready",      "generated": 14, "total": 14}
404 {"error": "not found"}
```

### `POST /sprints/<sprint_id>/day/<int:day_no>/complete`
Marks the day done, advances `current_day`/`phase`, recomputes the unlock meter and
momentum (streak + confidence). Completing Day 14 stamps `status=completed`.

```json
200 {"ok": true, "next_day": 5, "meter": {"completed_days": 4, "unlocked_count": 186,
     "total_in_cluster": 450, "last_delta": 38},
     "momentum": {"day_streak": 4, "confidence": 59}}
404 {"ok": false, "error": "not found"}
```

### `POST /mentor/turn`
Body: JSON `{"question": "..."}` (or form field). Returns a Socratic, job-grounded
answer — LLM first, deterministic guided template as fallback.

```json
200 {"answer": "...", "guided": true, "grounded_in": ["klaviyo", "checkout recovery"]}
200 {"answer": "Ask me anything about your target job.", "guided": true}
```

### Admin JSON (when `request.is_json` or `Accept: application/json`)
```json
201 {"cluster_key": "email-automation", "display_name": "Email Automation", ...}   // create cluster / feed / cohort
200 {"cluster_key": "email-automation", "job_count": 14, "avg_rate": 62,
     "unlock_days_assigned": 14}                                                    // POST /admin/clusters/<key>/refresh
403 {"error": "Admin access required"}
```

---

## 4. Key request forms (non-JSON POSTs)

| Endpoint | Fields | Writes |
|----------|--------|--------|
| `POST /sprints/request` | `skill` | `job_clusters` row in `requested` status |
| `POST /sprints/<key>/start` | — | `sprints` + `sprint_days` (14) + `copywork_projects` (3) + `sprint_unlock_snapshots`; joins/opens a cohort; spawns async content thread |
| `POST .../day/<n>/complete` | — | `sprint_days.is_done`, `sprints.current_day/phase`, meter + momentum |
| `POST .../day/<n>/copywork` | `rubric_url` | `verification_reviews (gate=A)`, `copywork_projects.done`, Gate A auto-pass |
| `POST .../contract/submit` | `submission_url` | `verification_reviews (gate=B)` + Gate B auto-pass |
| `POST .../contract/add` | `client_name`, `project_title`, `contract_value`, `your_rate`, `hours_worked`, `platform` | `contracts` + sprint roll-up (`contracts_won`, `total_earned`, `avg_contract_value`, `first_contract_at`) |
| `POST .../contract/<id>/complete` | — | `contracts.status=completed`, `sprints.contracts_completed += 1` |
| `POST .../case-study` | `title`, `problem`, `solution`, `result` | upsert `case_studies` (`is_draft` until Gate B passes) |
| `POST .../proposals/<pid>/submit` | `platform` | `proposals.status=submitted`, `sprints.proposals_sent += 1` (unverified platform rejected) |
| `POST .../proposals/<pid>/respond` | `outcome` ∈ `response` \| `interview` \| `offer` | `sprints.responses_received` / `interviews_held` / `offers_received` += 1 |
| `POST /admin/clusters/<key>/refresh` | — | `job_clusters` counters + `demand_snapshots` row + `job_feed.unlock_day` |
| `POST /auth/login` | `email` | `session["user_id"]` (real `auth.users` UUID only) |
