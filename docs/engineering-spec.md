# FreelanceLaunch — Engineering Specification

**Status:** Active · **Version:** 1.0 · **Last updated:** 2026-08-03 · **Owner:** Dhruba

> **Product:** A 30-day cohort accelerator that turns complete beginners into freelancers with their first paying client.
> **Codebase:** `web-app/` — Flask + Supabase monolith, deployed on Render (free tier).
> **Repository:** `web-app/` is the git repo root → `git@github.com:Djd11/freelancelaunch.git` (private, `origin` on `main`). Strategy docs (`engineering-spec.md`, `architecture.md`, `architecture.drawio`, business docs) live in the parent folder **outside** the repo.
> **Companion doc:** [`architecture.md`](./architecture.md) — system architecture + `architecture.drawio` (editable diagrams.net file).

---

## 1. Overview

FreelanceLaunch serves a 30-day, cohort-based curriculum per skill topic (web scraping, n8n automation, SEO content, pandas, WordPress, or any user-submitted topic). Each day has a Learn → Practice → Apply structure backed by two algorithm families:

1. **Curriculum generation algorithm** — an LLM generates 30 daily lessons using learning-science structure (hook, concept, practice, retrieval, spaced review, preview).
2. **Motivational algorithm** — streaks, nudges, confidence scores, and milestones keep users engaged through the "valley of despair" (days 8–14).

The platform tracks **two funnels**: *Funnel 1* (how users are acquired and convert to paid) and *Funnel 2* (how users land contracts and earn). The two funnels together power the product's core claim: *"X% of students land a client in Y days."*

**Key engineering constraint:** the entire platform must run on free-tier services ($0–15/mo). This drives the LLM fallback chain, pure-HTML video previews (no MP4 needed), and cohort-based video production (one video/night serves an entire cohort).

---

## 2. Goals & Non-Goals

### Goals
- **Server-side curriculum generation at ~$0** — use free/cheap LLM APIs (OpenRouter free models) with a resilient fallback chain.
- **No-500 philosophy** — every page degrades gracefully (fallback lessons, async generation, loading states) rather than erroring.
- **Video-first but render-optional** — a pure-HTML TwoPanel preview with TTS voiceover is served instantly; the heavier Remotion MP4 pipeline runs overnight for YouTube distribution.
- **Dual-funnel data capture** — every user action from signup to contract earnings is structured for analytics.
- **Cohort model** — one video production per day serves an unlimited number of users in that cohort.

### Non-Goals (MVP)
- ❌ Client-side curriculum generation (users don't bring API keys — conversion killer).
- ❌ Real-time Upwork/Fiverr scraping (curated topics + heuristic demand scoring instead).
- ❌ Automated YouTube upload via OAuth (currently a stub returning a placeholder video ID).
- ❌ Mobile app, multi-language content, or real-time chat/community features.
- ❌ Fine-grained Supabase RLS policies (MVP uses the `service_role` key to bypass RLS).

---

## 3. System Context

```
            ┌────────────────────────────────────────────────────────┐
            │  Browser (8 views: landing, topics, dashboard, day,    │
            │  pipeline, admin, pricing, search)                      │
            └───────────────────────┬────────────────────────────────┘
                                    │ HTTPS
                                    ▼
            ┌────────────────────────────────────────────────────────┐
            │  Flask App  (Render · gunicorn · 2 workers · wsgi.py)   │
            │  13 blueprints · session middleware · template globals   │
            └──────────┬──────────────────────┬──────────────────────┘
                       │ service-role API     │ checkout / webhooks
                       ▼                      ▼
            ┌─────────────────────┐   ┌──────────────┐
            │  Supabase           │   │  Stripe      │
            │  Postgres + Auth    │   └──────────────┘
            │  + Storage          │
            └─────────────────────┘
```

Background workers (services) touch LLM providers (OpenRouter → Hermes → Omniroute), edge-tts, Remotion, and YouTube — see [`architecture.md`](./architecture.md).

---

## 4. Tech Stack

| Layer | Technology | Version / Note |
|-------|-----------|----------------|
| **Backend** | Flask (app factory pattern) | `flask>=3.0` |
| **DB + Auth** | Supabase (Postgres + Auth) | `supabase>=2.0`, service-role key |
| **HTTP client** | `httpx` | LLM calls, async-capable |
| **Payments** | Stripe Checkout (+ Gumroad fallback) | `stripe>=7.0` |
| **TTS** | `edge-tts` (edge-tts CLI) | Voice: `en-US-ChristopherNeural` |
| **Video render** | Remotion 4.0.484 (local machine) | TwoPanel v2, 1920×1080 @ 30fps |
| **LLM** | OpenRouter free → env → Omniroute → Hermes | Model: `google/gemma-4-26b-a4b-it:free` |
| **Hosting** | Render (free) | gunicorn, 2 workers, runtime 3.11.8 |
| **Frontend** | Jinja2 + Tailwind CDN + vanilla JS | No build step |

---

## 5. Repository Layout (relevant subset)

> **Git repo root is `web-app/`** (`freelancelaunch.git`, branch `main`). The strategy docs below live in the parent folder and are **not** in the repo.

```
daily_learning_freelance/
├── business-plan.md                # product + revenue strategy
├── webapp-plan.md                  # original Next.js plan (superseded by Flask)
├── curriculum-generation-algorithm.md  # learning-science curriculum spec
├── motivational-algorithm.md       # psychology-based engagement spec
├── engineering-spec.md             # THIS DOCUMENT
├── architecture.md                 # architecture + draw.io link
├── architecture.drawio             # editable diagrams.net source
├── web-app/
│   ├── app.py                      # app factory, blueprint registry, middleware
│   ├── config.py                   # env-driven configuration
│   ├── schema.sql                  # canonical DB schema (run in Supabase SQL editor)
│   ├── wsgi.py                     # gunicorn entry + startup diagnostics/fallback
│   ├── Procfile / runtime.txt / requirements.txt / .env.example
│   ├── routes/                     # 13 blueprints
│   ├── services/                   # 8 services
│   ├── templates/                  # 17 Jinja2 templates
│   └── static/previews/            # cached TTS audio for HTML previews
└── educational-video-gen/          # Remotion TwoPanel v2 skill + references
```

---

## 6. Application Structure

### 6.1 App Factory (`app.py`)

`create_app()`:
1. Loads `config.Config` from environment.
2. Registers 13 blueprints.
3. `before_request` hook loads the user into `g.user` from `session["user_id"]` (Supabase lookup on `user_profiles`).
4. `context_processor` injects `user`, `platform_needs_setup`, `platform_count`, and `STRIPE_PUBLISHABLE_KEY` into every template.

### 6.2 Blueprints (routes)

| Blueprint | Prefix | Purpose | Key endpoints |
|-----------|--------|---------|---------------|
| `auth` | `/auth` | Email/password signup, login, logout, profile | `/signup`, `/login`, `/logout`, `/profile` |
| `topics` | `/topics` | Browse curated topics, view detail, enroll | `/`, `/<slug>`, `/<slug>/enroll` |
| `enroll_dynamic` | `/enroll` | Custom-topic enrollment (search → curriculum) | `/new` (POST, JSON) |
| `dashboard` | `/dashboard` | Main daily UX + day detail | `/`, `/day/<day_number>` |
| `progress` | `/api/progress` | Mark learn/practice/apply done, self-rate | `/mark`, `/rate` |
| `deliverables` | `/deliverables` | Portfolio submissions | `/submit`, `/portfolio` |
| `freelance` | `/freelance` | Funnel 2: pipeline + contracts | `/pipeline`, `/api/update`, `/contract/add` |
| `payments` | `/payments` | Tiers, Stripe checkout, success | `/pricing`, `/create-checkout`, `/success` |
| `admin` | `/admin` | Platform overview, user list, production | `/`, `/users`, `/production`, `/production/trigger/<id>` |
| `platforms` | `/platforms` | Upwork/Fiverr/Contra verification | `/setup`, `/api/select`, `/api/verify`, `/api/skip`, `/api/remove`, `/api/status` |
| `search` | `/search` | Demand search + suggestions | `/api`, `/suggestions`, `/curriculum/<slug>` |
| `generate_api` | `/api` | Async curriculum generation + progress | `/generate-curriculum/<slug>`, `/generation-status/<slug>`, `/generation-log/<slug>` |
| `preview` | `/preview` | HTML TwoPanel video preview w/ TTS | `/day/<day_number>` |

### 6.3 Services

| Service | Responsibility |
|---------|----------------|
| `supabase_client.py` | Singleton client factory (service-role key) |
| `curriculum_generator.py` | 5-phase LLM pipeline + platform-specific modules + deterministic fallback lessons |
| `nudge_engine.py` | Streak computation, confidence score, nudges, milestones, encouragement messages |
| `preview_generator.py` | Builds the animated HTML TwoPanel preview page + edge-tts TTS |
| `video_script_generator.py` | LLM → 9-section voiceover script + 9-panel content for Remotion |
| `panel_content_writer.py` | Writes `PanelContent.js` (panels, timing, keywords) into the Remotion project |
| `render_worker.py` | Full overnight pipeline orchestrator (script → TTS → panels → render → upload) |
| `scheduler.py` | 2 AM cron — finds active cohorts, produces next day's video |
| `youtube_uploader.py` | YouTube upload (stub — returns placeholder ID, pending OAuth) |

---

## 7. Database Schema (Supabase Postgres)

Canonical DDL: [`schema.sql`](../schema.sql). Tables grouped by function:

**Funnel 1 — Acquisition**
| Table | Purpose |
|-------|---------|
| `user_acquisition` | Source, UTM, referrer, signup/cohort/paid timestamps, LTV, tier |
| `topics` | Curated + user-submitted topics, demand_score, job_count, avg_rate |
| `curricula` / `curriculum_days` | One 30-day curriculum per topic; per-day lesson content |
| `cohorts` | Topic-scoped cohort with start/end dates, current_day, status |
| `cohort_videos` | One video per day per cohort; production_status + YouTube refs |
| `user_profiles` | Display name, cohort_id, tier, selected_topic_id, onboarding flag |
| `user_platforms` | Upwork/Fiverr/Contra link + verification status |

**Funnel 2 — Outcome**
| Table | Purpose |
|-------|---------|
| `user_progress` | Per-day video_watched / practice_completed / apply_completed / self_rating |
| `deliverables` | User submissions (blog, code, proposal, …) |
| `freelance_pipeline` | Stage (exploring → … → completed) + proposal/contract/earnings counters |
| `contracts` | Client, value, hours, payment status |
| `topic_intelligence` | Aggregated demand + placement metrics per topic (viability_score) |

**Operations**
| Table | Purpose |
|-------|---------|
| `curriculum_generation_log` | DB-backed async generation progress (cross-worker visibility) |
| `video_production_log` | Step-by-step video production audit trail |

**Key relationships:** `cohorts.topic_id → topics.id`, `cohort_videos.curriculum_day_id → curriculum_days.id`, `user_progress.cohort_video_id → cohort_videos.id`, `freelance_pipeline.topic` stores the topic **slug** (string) while `user_profiles.selected_topic_id` / `cohorts.topic_id` store the **UUID** — enrollment code must resolve slug → UUID before FK writes.

---

## 8. Core Flows

### 8.1 User journey
```
Landing → Signup (Supabase Auth) → Choose topic → Enroll
  → (async curriculum generation starts) → Platform verification (Upwork/Fiverr/Contra)
  → Dashboard (today's day, video, learn/practice/apply) → Freelance pipeline
  → Contract tracking → Paid tier (Stripe) or upsell
```

### 8.2 Async curriculum generation (`generate_api` + `curriculum_generator`)
1. `POST /api/generate-curriculum/<slug>` verifies auth + enrollment (pipeline record OR cohort membership).
2. Guard against duplicate runs (in-memory tracker + DB status check).
3. Spawns a `threading.Thread` running `_generate_in_background`, which iterates days 1–30:
   - `_generate_one_day()` → LLM lesson (6 sections) or deterministic `_fallback_lesson()`.
   - Each day is persisted to `curriculum_days` + a `cohort_videos` row is created so day links resolve.
   - Progress + structured log lines are written to `curriculum_generation_log` after every day.
4. Frontend polls `/generation-status/<slug>` (fast in-memory path) and `/generation-log/<slug>` (full structured log).

### 8.3 HTML video preview (`preview` + `preview_generator`)
`GET /preview/day/<N>` → build voiceover from the curriculum day → `edge-tts` generates `static/previews/day_N.mp3` (cached) → a self-contained HTML page renders with an animated SVG flow diagram (Learn → Practice → Apply), keyword chips, and word-by-word kinetic text synced to audio. **No MP4 render required.**

### 8.4 Nightly video production (`scheduler` → `render_worker`)
Runs at 2 AM (local cron):
1. Find active cohorts → tomorrow's day → curriculum record.
2. `produce_day_video()`: script + 9 panels (LLM) → TTS → write `PanelContent.js` → Remotion render → YouTube upload (stub) → DB status `ready`.
3. Production steps are logged to `video_production_log`.

### 8.5 Payments (`payments`)
`POST /payments/create-checkout` → Stripe Checkout session for Guided ($49) or Placement ($199) → redirect → `/payments/success` verifies session, upgrades `user_profiles.tier` + `user_acquisition`. Gumroad URL is the fallback when Stripe is unconfigured.

---

## 9. LLM Integration & Fallback Chain

`_call_llm()` (in `curriculum_generator.py`) resolves providers in priority order — **first one with an API key wins**:

1. **OpenRouter free** — `google/gemma-4-26b-a4b-it:free` (no key required to attempt).
2. **vision-tool config** — `~/Documents/vision-tool/config.json` → `OPENROUTER_API_KEY`.
3. **Env vars** — `LLM_API_URL` / `LLM_API_KEY` / `LLM_MODEL` (set on Render).
4. **Omniroute local** — `127.0.0.1:20128` (socket probe, 0.5 s timeout).
5. **Hermes / OpenCode.ai** — `~/.hermes/config.yaml`.

If **all** fail → `_fallback_lesson()` returns deterministic structured content so the day still renders. LLM call parameters: `temperature=0.7`, `max_tokens=4096`, `timeout=20 s`. Quality-scoring (Phase 3) is implemented as a prompt but currently passes lessons through for the MVP.

> ⚠ `generate_api._get_llm_config()` has a *separate* (parallel) provider-resolution chain — keep both in sync when changing LLM sources.

---

## 10. Background Jobs & Concurrency

| Job | Trigger | Mechanism | Notes |
|-----|---------|-----------|-------|
| Curriculum generation | POST /api/generate-curriculum | `threading.Thread` (daemon) | Progress is **DB-backed** (`curriculum_generation_log`) so it survives across gunicorn workers |
| Video production | `scheduler.py` (cron 2 AM) or admin button | `produce_day_video()` | Long-running (Remotion ~50–60 min on Intel HD 3000) |
| In-memory progress tracker | — | module-level dict `_progress_tracker` | Fast path on the same worker; DB is the source of truth |

**Caveat:** gunicorn runs 2 workers → threads spawned in one worker aren't visible to the other. The code already handles this via the DB-backed generation log; the in-memory dict is only an optimization.

---

## 11. Configuration (`.env` / Render env vars)

See [`.env.example`](../.env.example). Notable keys:

| Key | Purpose |
|-----|---------|
| `SECRET_KEY` | Flask session signing |
| `SUPABASE_URL` / `SUPABASE_KEY` / `SUPABASE_SERVICE_KEY` | DB + Auth access |
| `LLM_API_URL` / `LLM_API_KEY` / `LLM_MODEL` | LLM fallback (env) |
| `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY` / `STRIPE_WEBHOOK_SECRET` | Payments |
| `STRIPE_GUIDED_PRICE_ID` / `STRIPE_PLACEMENT_PRICE_ID` | Checkout price IDs |
| `GUMROAD_TOKEN` / `GUMROAD_GUIDED_URL` / `GUMROAD_PLACEMENT_URL` | Payment fallback |
| `YOUTUBE_API_KEY` | YouTube (stub) |
| `REMOTION_PROJECT_DIR` | Local Remotion project path |
| `RENDER_EXTERNAL_URL` | Canonical app URL |
| `ADMIN_EMAIL` | Admin panel gate |
| `PORT` | gunicorn bind port |

---

## 12. Deployment

- **Host:** Render free tier. `Procfile`: `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`.
- **Entry:** `wsgi.py` wraps `create_app()` with import diagnostics and a **fallback error app** that renders the startup traceback instead of a blank 500.
- **Runtime:** `python-3.11.8` (`runtime.txt`).
- **Database:** run `schema.sql` in the Supabase SQL Editor. Table creation is idempotent (`IF NOT EXISTS`).
- **Version control:** `web-app/` is the git repo root, remote `git@github.com:Djd11/freelancelaunch.git` on `main`. Commit conventions: conventional commits (`feat:`, `fix:`, `refactor:`). Docs in the parent folder are not versioned here.

---

## 13. Resilience & Error Handling

- **No-500 philosophy:** day pages auto-trigger generation when curriculum is missing; preview redirects back to the day page; admin counts swallow per-table errors.
- **LLM failure:** deterministic fallback lessons; generation continues past a failed day (logged as `error`, not fatal).
- **DB schema drift:** `_update_genlog()` falls back to `video_production_log` when `curriculum_generation_log` doesn't exist yet (PGRST205).
- **Missing curriculum/cohort:** redirects to topic selection instead of crashing.
- **Startup failure:** `wsgi.py` serves the traceback page for debuggability.

---

## 14. Security Considerations

| Concern | Current state | Recommendation |
|---------|---------------|----------------|
| Supabase RLS | Bypassed via service-role key in client | Enforce RLS policies before multi-tenant launch; keep service key server-side only |
| Admin access | `ADMIN_EMAIL` match against `avatar_url` (email stored there) | Move to a proper `is_admin` flag / role |
| Session | Flask cookie session storing `user_id` + Supabase token | Fine for MVP; add token refresh + expiry handling |
| Secrets | `.env` present in repo dir; `.env.example` documents keys | Never commit real `.env` |
| Payments | `payment_success` upgrades tier directly after Stripe retrieve | Add webhook verification for production |

---

## 15. Cost Analysis (free-tier target)

| Item | Cost |
|------|------|
| LLM (OpenRouter free / fallback) | ~$0 (free models) |
| Render hosting | $0 (free tier) |
| Supabase | $0 (free tier) |
| edge-tts / Remotion | $0 (local) |
| Stripe | 2.9% + $0.30 per transaction |
| **Total fixed** | **~$0–15/mo** |

---

## 16. Testing Strategy

- **Current:** `seed_test_data.py` creates an admin user + seed data; manual QA via the dashboard.
- **Planned (from `course-curation-strategy.md` Phase D, not yet implemented):** BDD suite (`behave`) covering:
  - Curriculum includes platform days when platforms are linked.
  - Platform training order matches demand priority.
  - Proposal exercise loads a real Upwork job.
  - Profile checklists track completion per platform.
- **Gap:** no automated tests for routes/services yet. Priority targets: `nudge_engine` (pure functions — easy unit tests), `curriculum_generator` parsing, `preview_generator` HTML output.

---

## 17. Known Gaps & Risks

1. **Strategy docs not versioned** — `web-app/` is the git root; business/engineering/architecture docs live in the parent folder outside the repo. Consider committing them into a `docs/` folder at the repo root (or a second repo) so design history is preserved.
2. **YouTube upload is a stub** — `youtube_uploader.py` returns a hash-based placeholder ID. Requires OAuth 2.0 setup.
3. **Service-role key exposure** — used in every request; must move behind RLS before launch.
4. **`avatar_url` doubles as the email column** — legacy shortcut; separate the fields.
5. **Thread-in-worker state** — in-memory progress tracker is per-worker; DB fallback mitigates but verify behavior with 2 workers.
6. **Heuristic demand data** — `search.py` uses keyword scoring, not live platform data.
7. **Scheduler runs on the local machine** — not part of the Render deployment; document the operational dependency.

---

## 18. Roadmap

| Phase | Scope |
|-------|-------|
| **Current (MVP)** | Auth, topics, enrollment, async curriculum, dashboard, progress, platforms, pipeline, HTML previews, Stripe tiers |
| **Phase 2** | Real YouTube OAuth upload, automated email digests (Resend), follow-up reminders, quality-scoring gate enabled, BDD test suite |
| **Phase 3** | Adaptive difficulty (progress-based lesson regeneration), accountability pairing, leaderboards, RLS policies |
| **Phase 4** | Playwright demand scraper, topic intelligence dashboard, multi-language, mobile-responsive polish |

---

*References: `webapp-plan.md`, `curriculum-generation-algorithm.md`, `motivational-algorithm.md`, `cost-efficiency-analysis.md`, `.hermes/plans/*`, and the `web-app/` source itself.*
