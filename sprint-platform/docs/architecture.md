# FreelanceLaunch · Sprint Platform — Architecture (v1)

**Status:** New project · **Version:** 1.0 · **Date:** 2026-08-11 · **Owner:** Dhruba
**Product truth:** [`../../mockups/product-mockup.html`](../../mockups/product-mockup.html)
**Companions:** [`engineering-spec.md`](./engineering-spec.md) · [`../db/schema.sql`](../db/schema.sql) · [`bdd/`](./bdd/)

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
| 2 | **No-500 philosophy** | Every user-facing path degrades gracefully (fallback lessons, async generation, deterministic proposal templates, "thinking…" mentor fallback) |
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
 │   main · sprints · day · contract · proposals · profile          │
 │   mentor · client-filter · admin · pricing (later)               │
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
 │ External: LLM fallback · edge-tts  │  (Remotion/YouTube deferred)
 └────────────────────────────────────┘
```

---

## 4. Layered architecture

### 4.1 Browser layer
Server-rendered Jinja2 views (Tailwind CDN + vanilla JS/Alpine). Screens mirror the mockup 1:1: landing, sprint picker, sprint dashboard (with meter + momentum), day view, mock contract, proposal builder, public profile, AI mentor, client filter, admin. No SPA — landing/topic surfaces render server-side for SEO.

### 4.2 Application layer (Flask blueprints)
| Blueprint | Routes | Purpose |
|-----------|--------|---------|
| `main` | `/`, `/sprints` | Landing, sprint picker, request-a-sprint |
| `sprints` | `/sprints/<id>`, day, complete | Dashboard, phase/day views, day completion + meter uptick |
| `contract` | `/sprints/<id>/contract[/submit]` | Mock Contract brief + verification gate |
| `proposals` | `/sprints/<id>/proposals`, submit | First-Bid challenge + engineered proposals |
| `profile` | `/profile/<user>`, `/profile/me` | Public demand profile + badges + portfolio |
| `mentor` | `/mentor`, `/mentor/turn` | AI mentor chat |
| `clients` | `/clients/freelancers` | Badge-filtered freelancer search |
| `admin` | `/admin/*` | Feed curation, cohort creation, peer-review queue |
| `auth` | `/auth/*` | Signup/login (Supabase Auth) |

### 4.3 Service layer (workers)
Pure-ish Python modules callable in-request (nudge, meter recompute, mentor) and in-thread/cron (plan generation, feed ingest, badge recompute).

| Service | Responsibility |
|---------|----------------|
| `demand_intelligence` | Feed ingest, normalize, cluster, score, `unlock_day` bucketing, live counters, snapshots |
| `sprint_planner` | 14-day plan generation (async, DB-backed) |
| `copywork_engine` | Select/sequence 3 replication projects + gap-fill detection |
| `gap_fill_engine` | Detect missing nuance from rubric results → Day-5 micro-lesson |
| `mock_contract_engine` | Anonymized brief match + deadline/constraint enforcement |
| `verification_service` | Gates A & B: auto-check (code) / peer queue (design, copy) |
| `proposal_engine` | Hook templates + proof-from-contract + completeness scoring |
| `iteration_engine` | Day-14 diagnosis: price/portfolio/niche → remedial micro-course |
| `unlock_engine` | Meter recompute on day completion + snapshot write |
| `badge_engine` | Demand-Validated badge issuance + live counters |
| `mentor_agent` | Job-grounded Socratic RAG chat |
| `nudge_engine` | Streak + confidence + encouragement on progress marks |
| `outcome_service` | Contract add/complete; recompute `total_earned`, `avg_contract_value`, etc. |

### 4.4 Data layer (Supabase)
`db/schema.sql` — Postgres dual-funnel-free schema (sprint owns outcomes). Auth + Storage beside the DB. Access via service-role client for MVP.

### 4.5 External integrations
LLM providers (fallback chain), edge-tts (HTML preview voiceover). Remotion/YouTube deferred out of v1.

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

### 5.2 Enroll → plan generation (async)
```
User: POST /sprints/new {cluster_key}
  → resolve cluster (job_count, avg_rate)
  → create cohort (or join existing active cohort)
  → create sprints row + sprint_unlock_snapshots
  → sprint_planner spawns background thread → 14 sprint_days (DB-backed log)
  → dashboard: "Day 1 · Phase A · Copy-Work" + meter
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

### 5.4 Verification gates
```
Gate A: 3 copy-work rubrics + gap-fill done → POST contract/gate-a → verification_reviews(gate=A) auto-check → pass → Phase B unlocked
Gate B: POST contract/submit (deliverable URL) → verification_service auto/peer → verification_reviews(gate=B) pass → Phase C unlocked
```

### 5.5 Proposal submit → outcome counters
```
User: POST /sprints/<id>/proposals/<pid>/submit {platform}
  → proposals.status='submitted', platform recorded
  → sprints.proposals_sent += 1 (scoped by sprint_id + user_id)
  → iteration_engine.diagnose() if proposals_sent >= 5 and responses_received == 0
```

### 5.6 Contract add → earnings roll-up
```
User: POST /sprints/<id>/contract/add {client, value, hours, platform}
  → contracts row (sprint_id)
  → outcome_service: contracts_won += 1, total_earned += value,
    avg_contract_value = total_earned/contracts_won, first_contract_at (if none)
  → badge page reflects "1 interview · 1 contract"
```

### 5.7 Public profile + client filter
```
Client: GET /profile/<user>
  → user_profiles + badges + live counters (job_clusters) + trend (demand_snapshots)
Client: GET /clients/freelancers?cluster=email-automation&within_days=30
  → public_freelancers view → list of fresh verified freelancers
```

---

## 6. LLM fallback chain (same as v1 — keep in sync with llm_config)

```
_call_llm():
  1. OpenRouter free (no key)
  2. vision-tool config.json (OPENROUTER_API_KEY)
  3. env vars (LLM_API_URL / LLM_API_KEY / LLM_MODEL)
  4. Omniroute local (127.0.0.1:20128, socket probe)
  5. Hermes / OpenCode.ai (~/.hermes/config.yaml)
  6. ❌ → deterministic fallback (lessons, proposal templates, mentor "thinking…")
```
The app never 500s on a missing API key.

---

## 7. Async & concurrency

| Job | Trigger | Mechanism |
|-----|---------|-----------|
| Sprint plan generation | POST /sprints/new | background thread, DB-backed log + polling |
| Gap-Fill detection | per copy-work completion | inline (short) |
| Badge counter recompute | daily cron | `badge_engine` |
| Feed refresh / demand snapshots | nightly cron | `demand_intelligence` |
| Verification (auto) | contract submit | inline auto-test |
| Verification (peer) | contract submit | enqueued review queue |

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

*References: `engineering-spec.md`, `db/schema.sql`, `bdd/*.feature`, `../../mockups/product-mockup.html`.*
