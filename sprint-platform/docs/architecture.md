# FreelanceLaunch · Sprint Platform — Architecture (v1)

**Status:** New project · **Version:** 1.1 · **Date:** 2026-08-16 · **Owner:** Dhruba
**Product truth:** [`./mockups/product-mockup.html`](./mockups/product-mockup.html)
**Companions:** [`engineering-spec.md`](./engineering-spec.md) · [`api.md`](./api.md) · [`../db/schema.sql`](../db/schema.sql) · [`bdd/`](./bdd/)

---

## 1. Overview

A **server-rendered Flask monolith** on **Supabase (Postgres + Auth)**, with background workers that turn LLM output into 14-day sprint plans, auto-checked rubrics, engineered proposals, and job-grounded mentorship. The architecture is deliberately boring: free-tier hosting, no build step, no microservices. It is a **fresh codebase** — the v1 app, its `freelance_pipeline`, and the 30-day curriculum are not carried over.

Three pillars:
1. **Demand-first data** — every sprint is generated from a live job cluster; the feed, badges, and Unlock Meter read the same `job_feed`/`job_clusters` source of truth.
2. **Motivation via unlocking** — the Job Unlock Meter converts abstract demand numbers into a fillable per-day reward.
3. **Fulfillment gate** — the Mock Contract must pass verification before bidding; the sprint's badge is therefore credible to clients.

---

## 2. Architecture principles

| # | Principle | Consequence |
|---|-----------|-------------|
| 1 | **Free-tier economics** | Everything on $0–15/mo: Render free, Supabase free, OpenRouter free models, local HTML previews |
| 2 | **No-500 philosophy** | Requests never crash. Generated content is LLM-only: LLM failure surfaces a visible error (`generation_error` on the day payload, 503 on the mentor turn) — never template content. Async generation, deterministic proposal templates, and the "thinking…" loading state stay. |
| 3 | **Cohort amortization** | Generate one sprint plan per cluster; users in a cohort share content, each keeps their own day counter |
| 4 | **Sprint owns the outcome** | `sprints` is the single source of truth for proposals → contracts → earnings. No separate pipeline module |
| 5 | **Async generation** | Long LLM work is backgrounded, DB-persisted, and polled — never blocks a request |
| 6 | **Public marketing surface** | Badge + job counters are public reads pre-launch — they *are* the acquisition hook |
| 7 | **Single deployable** | Flask monolith + service layer; workers are functions, not separate servers |

---

## 3. System context

```
 Browser (views: landing, picker, sprint, day, contract, proposals, profile, mentor, client filter)
        │ HTTPS
        ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │ Flask App (blueprints)                                          │
 │   main · sprints · contract · proposals · profile · mentor       │
 │   clients · admin · auth · pricing (later)                       │
 └───────┬───────────────────┬───────────────────┬─────────────────┘
         ▼                   ▼                   ▼
 ┌──────────────┐   ┌─────────────────┐   ┌───────────────────┐
 │ DEMAND-INTEL │   │ SPRINT ENGINES   │   │ SUPPORT ENGINES    │
 │ feed ingest  │   │ sprint_planner   │   │ nudge · mentor ·   │
 │ clustering   │   │ copywork · mock  │   │ badge · verification│
 │ unlock_day   │   │ contract · prop- │   │ iteration · outcome │
 │ scoring      │   │ osal · gap-fill  │   │                    │
 └──────┬───────┘   └────────┬────────┘   └─────────┬──────────┘
        ▼                   ▼                      ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │ Supabase  — Postgres (schema.sql) · Auth · Storage                │
 │  job_clusters · job_feed · demand_snapshots · cohorts · sprints   │
 │  sprint_days · copywork_projects · capstone_briefs · proposals    │
 │  verification_reviews · contracts · badges · unlock_snapshots     │
 │  user_momentum · mentor_sessions · public_freelancers (view)      │
 └─────────────────────────────────────────────────────────────────┘
        ▲
        │  (only the service layer talks to LLM / external)
 ┌──────┴─────────────────────────────┐
 │ External: LLM provider chain · edge-tts  │  (Remotion Player in-browser · YouTube deferred)
 └────────────────────────────────────┘
```

---

## 4. Layered architecture

### 4.1 Browser layer
Server-rendered Jinja2 views (Tailwind CDN + vanilla JS/Alpine). Screens mirror the mockup 1:1: landing, sprint picker, sprint dashboard (with meter + momentum), day view, mock contract, proposal builder, public profile, AI mentor, client filter, admin. No SPA — landing/topic surfaces render server-side for SEO.

### 4.2 Application layer (Flask blueprints)
| Blueprint | Routes | Purpose |
|-----------|--------|---------|
| `main` | `/`, `/topics`, `/sprints`, `/sprints/request`, `/sprints/<cluster_key>/start` (POST), `/pricing`, `/dashboard/` | Landing, topics nav, sprint picker, request-a-sprint, **enrollment** (sprint + cohort + plan skeleton + async content) |
| `sprints` | `/sprints/<id>`, `/day/<n>`, `/generation`, `/day/<n>/complete`, `/day/<n>/copywork`, `/complete`, `/badge` | Dashboard, day views, **generation progress (JSON)**, day completion + meter uptick, Gate A submit, explicit sprint completion, badge issuance |
| `contract` | `/sprints/<id>/contract`, `/contract/submit`, `/contract/add`, `/contract/<id>/complete`, `/case-study` | Mock Contract brief + Gate B, contracts roll-up, Problem/Solution/Result case study |
| `proposals` | `/sprints/<id>/proposals`, `/proposals/<pid>/submit`, `/proposals/<pid>/respond` | First-Bid challenge, human-initiated submission, **outcome logging** |
| `profile` | `/profile/<slug>`, `/profile/me` | Public demand profile + badges + portfolio |
| `mentor` | `/mentor`, `/mentor/turn` | AI mentor chat |
| `clients` | `/clients/freelancers` | Badge-filtered freelancer search (`public_freelancers` view) |
| `admin` | `/admin/*` — clusters, feed, cohorts, `POST /clusters/<key>/refresh` | Feed curation, cohort creation, **demand refresh + snapshots** |
| `auth` | `/auth/login` (GET/POST), `/auth/logout` | Session login (Supabase Auth) |

Full endpoint reference: [`api.md`](./api.md).

### 4.3 Service layer (workers)
Pure-ish Python modules callable in-request (nudge, meter recompute, mentor) and in-thread/cron (plan generation, feed ingest, badge recompute).

| Service | Responsibility |
|---------|----------------|
| `llm` | The **one shared LLM provider chain** (`call_llm`): env → OpenRouter → Omniroute local → `None` → callers raise `LLMGenerationError` (content is LLM-only) |
| `demand_intelligence` | Feed ingest, normalize, cluster, score, `unlock_day` quantile bucketing, live counters, demand snapshots |
| `sprint_planner` | 14-day skeleton (`sprint_days` phase/action map) — synchronous, idempotent upsert |
| `lesson_engine` | Per-day lesson + project anatomy (clone steps/rubric) — **LLM-only** (no deterministic content); **the async worker** (`generate_sprint_content`) + progress count; on LLM failure stamps a visible `generation_error` on a day payload (never template content). Day 5's lesson is the targeted Gap-Fill micro-lesson on the flagged nuance |
| `video_engine` | Two-panel lesson voiceover — edge-tts synthesizes the lesson script, ffprobe measures duration, MP3 uploaded to the `voiceovers` Supabase Storage bucket; called from the async content worker, best-effort (None → kinetic-text fallback) |
| `copywork_engine` | Seeds the 3 replication-project placeholder **skeleton** (mockup titles/source, empty `clone_steps`/`rubric`) + `gap_fill_topic` on project 2 — the worker fills the anatomy via LLM so content matches the learner's actual cluster, not a hard-coded email template |
| `mock_contract_engine` | Anonymized brief synthesis from the cluster's first active posting (No-500 default) |
| `verification_service` | Gates A & B: `auto_check_gate_a/b` inline auto-tests (3 projects done + valid submitted URLs / valid deliverable URL + case study saved) + peer pass via `record()` |
| `proposal_engine` | Hook templates + proof-from-contract + completeness scoring |
| `iteration_engine` | Diagnosis: price/portfolio/niche from the sprint's own data → remedial micro-course |
| `unlock_engine` | Meter recompute on day completion + snapshot write |
| `badge_engine` | Demand-Validated badge issuance (gate B pass + completed sprint, idempotent) |
| `mentor_agent` | Job-grounded Socratic chat — LLM-only with grounding check; ungrounded or unavailable → visible error, never a canned answer |
| `nudge_engine` | Streak + confidence recompute + encouragement on progress marks |
| `outcome_service` | Contract add/complete; recompute `total_earned`, `avg_contract_value`, `first_contract_at`, `contracts_completed` |

### 4.4 Data layer (Supabase)
`db/schema.sql` — Postgres dual-funnel-free schema (sprint owns outcomes). Auth + Storage beside the DB. Access via service-role client for MVP.

### 4.5 External integrations
LLM providers (provider chain — availability redundancy only, no deterministic content), edge-tts (two-panel lesson voiceover), and a pre-built Remotion Player bundle (`static/video/lesson-player.js`) served by Flask — the day view plays the composition in-browser (kinetic text + TTS, no MP4). YouTube distribution deferred out of v1.

---

## 5. Key data flows

### 5.1 Request a sprint → cluster curated → sprint picker shows live badge
```
Client: POST /sprints/request {skill}
  → admin/ops curates job_feed for the cluster
  → demand_intelligence: cluster + score + unlock_day buckets
  → job_clusters.job_count refreshed
Picker: GET /sprints → job_clusters (live counters)
```

### 5.2 Enroll → plan skeleton + async content generation
```
User: POST /sprints/<cluster_key>/start   (POST-only — no GET side effects)
  → resolve cluster (job_count, avg_rate)
  → join latest active cohort for the cluster, else open a new Cohort #N (14 days)
  → create sprints row + sprint_unlock_snapshots
  → create_plan() → 14 sprint_days rows (skeleton, sync — request never waits)
  → create_projects() → 3 copywork_projects placeholder skeleton (sync; mockup
    titles/source, empty anatomy)
  → background thread: lesson_engine.generate_sprint_content() fills each day's
    action_payload.lesson + project anatomy (LLM-only — no deterministic content;
    on failure stamps a visible generation_error on a day payload); the
    populated-payload count IS the DB progress log
  → dashboard: "Day 1 · Phase A · Copy-Work" + meter; polls /sprints/<id>/generation
    ({status, generated, total}) and hides the spinner at "ready"; on
    generation_error the poll shows "Content generation failed"
```

### 5.3 Day completion → meter uptick + momentum
```
User: POST /sprints/<id>/day/<n>/complete
  → mark sprint_days.is_done
  → advance sprints.current_day/phase
  → unlock_engine.recompute → sprint_unlock_snapshots {newly:+38, total:186, cluster:450}
  → nudge_engine recompute (streak, confidence)
  → JSON {ok, next_day, meter, momentum}
  → UI celebratory uptick banner
```

### 5.4 Verification gates (inline auto-checks)
```
Gate A: POST /sprints/<id>/day/<n>/copywork {rubric_url (valid http(s), required)}
  → mark copywork_projects.done + submitted_url for the day's project
  → auto_check_gate_a: all 3 projects done AND each has a valid submitted URL → verification_reviews(gate=A) = pass → Phase B unlocked
Gate B: POST /sprints/<id>/contract/submit {submission_url (valid http(s), required)}
  → record pending review, then auto_check_gate_b: valid deliverable URL + a saved case study
  → verification_reviews(gate=B) = pass → Phase C unlocked
Peer review (design/copy): manual pass written through record() by an admin.
```

### 5.5 Proposal submit + outcome logging
```
User: POST /sprints/<id>/proposals/<pid>/submit {platform}
  → proposals.status='submitted', platform recorded (unverified platform rejected)
  → sprints.proposals_sent += 1 (scoped by sprint_id + user_id)
User: POST /sprints/<id>/proposals/<pid>/respond {outcome: response|interview|offer}
  → sprints.responses_received / interviews_held / offers_received += 1
Proposals page: iteration_engine.diagnose() rendered when proposals_sent >= 5
  and responses_received == 0 → named bottleneck + remedial micro-course
```

### 5.6 Contract add/complete → earnings roll-up
```
User: POST /sprints/<id>/contract/add {client, value, hours, platform}
  → contracts row (sprint_id)
  → outcome_service.add_contract: contracts_won += 1, total_earned += value,
    avg_contract_value = total_earned/contracts_won, first_contract_at (UTC stamp if none)
User: POST /sprints/<id>/contract/<id>/complete
  → outcome_service.complete_contract: contracts.status='completed',
    sprints.contracts_completed += 1
  → dashboard Contracts & Earnings card + badge page reflect the roll-up
```

### 5.7 Public profile + client filter
```
Client: GET /profile/<user>
  → user_profiles + badges + live counters (job_clusters) + trend (demand_snapshots)
Client: GET /clients/freelancers?cluster=email-automation&within_days=30
  → public_freelancers view → list of fresh verified freelancers
```

---

## 6. LLM provider chain — `services/llm.py call_llm`

```
call_llm(prompt):
  1. env-configured endpoint (LLM_API_URL / LLM_API_KEY / LLM_MODEL)
  2. OpenRouter (OPENROUTER_API_KEY / OPENROUTER_MODEL)
  3. Omniroute local (127.0.0.1:20128, socket probe)
  4. ❌ → None → caller raises LLMGenerationError → the UI surfaces a visible
     error (generation_error on the day payload / 503 on the mentor turn)
```
Every step is try/except with short timeouts. **Content is LLM-only: there is no
deterministic content fallback.** Provider redundancy exists for availability
only — a missing key or unreachable provider becomes a visible generation error,
never silent template content. Callers validate LLM output (e.g. `mentor_agent._grounded`
requires the answer to echo the job's terminology) and raise on failure.

---

## 7. Async & concurrency

| Job | Trigger | Mechanism |
|-----|---------|-----------|
| Sprint content generation | `POST /sprints/<cluster_key>/start` | background thread, populated-payload count = DB log, `GET /sprints/<id>/generation` polling; each day's lesson also gets an edge-tts voiceover (`video_engine`) stored in the `voiceovers` Storage bucket |
| Gap-Fill detection | project 2 anatomy (deterministic in v1) | inline — `gap_fill_topic` on the day view |
| Badge issuance | `GET /sprints/<id>/badge` (after completion) | `badge_engine`, idempotent (gate B pass + completed) |
| Feed refresh / demand snapshots | admin `POST /admin/clusters/<key>/refresh` or nightly cron | `demand_intelligence` |
| Verification (auto) | copy-work submit (Gate A) / contract submit (Gate B) | inline auto-check (`auto_check_gate_a/b`) |
| Verification (peer) | admin manual pass | `verification_service.record()` |

---

## 8. Deployment topology

```
┌─────────────── Internet ───────────────┐
│  Browser ──HTTPS──► Render (free tier) │
│                      gunicorn · 2 wk   │
│                      Flask · wsgi.py   │
│                            │           │
│                            ▼           │
│                    Supabase (cloud)    │
└───────────┬──────────────────────┬─────┘
            │                      │
   local dev machine           Render env vars
   nightly crons               (SECRET_KEY, SUPABASE_*, LLM_*, ADMIN_EMAIL)
```

- App: Render free tier, gunicorn 2 workers, 120s timeout.
- DB: Supabase; `db/schema.sql` applied idempotently.
- Cron workers run locally (developer machine) or via a free scheduler.
- Secrets via env vars; `.env` locally.

---

## 9. Scaling considerations

| Constraint | Current | When to act |
|-----------|---------|-------------|
| Render free tier | 512 MB, 2 workers | Move to paid at ~concurrent load |
| Supabase free | 500 MB DB, 2 GB bandwidth | Move to Pro at ~500 users |
| gunicorn worker state | in-memory progress is per-worker (DB is source of truth) | verify with 2 workers |
| Meter reads | `sprint_unlock_snapshots` O(1) | at >1k concurrent, cache counters |
| LLM throughput | free tier rate limits | add queue + retry/backoff at scale |

---

*References: `engineering-spec.md`, `db/schema.sql`, `bdd/*.feature`, `./mockups/product-mockup.html`.*
