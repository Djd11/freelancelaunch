# FreelanceLaunch — Sprint Track Engineering Spec (v2.1)

**Status:** Approved & building · **Version:** 2.1 · **Date:** 2026-08-09 · **Owner:** Dhruba
**Branch:** `sprint-track` (this is the parallel placement track; v1 30-day curriculum remains untouched and runs alongside)
**Basis:** [`research_material.txt`](../../../research_material.txt) · research is the product thesis
**Companions:** [`architecture.md`](./architecture.md) · [`schema_v2.sql`](../../schema_v2.sql) · BDD specs in [`tests/features/sprint/`](../../tests/features/sprint/)

> **Parallel-track decision:** the sprint is an *accelerated, demand-validated placement track* that coexists with the v1 deep-dive curriculum. We ship both, measure both against placement + retention, and keep or discard each on evidence — nothing is removed.

---

## 1. Product model — the 14-day Demand-Validated Sprint

A **Sprint** is a 14-day, cohort-scoped program whose only goal is *get a response or contract in this skill*. Three phases map 1:1 to the research:

| Phase | Days | Research anchor | Outcome gate |
|-------|------|-----------------|--------------|
| **A · Skill Acquisition** | 1–5 | Copy-Work Method | 3 replication projects + gap-fill micro-lesson |
| **B · Mock Contract** | 6–10 | Fulfillment simulation | Verified capstone deliverable (auto/peer) |
| **C · Supply Chain** | 11–14 | Proposal + First Bid | 5 live proposals → iteration loop |

Each phase **locks the next behind a verification gate** — you cannot enter the job-feed bid stage until the Mock Contract passes review.

Running alongside the phases is the **Job Unlock Meter** (§2), the daily motivational engine.

```
Day 1-5 ─ Copy-Work ──► Day 6-10 ─ Mock Contract ──► Day 11-14 ─ Proposals ──► Client
   Phase A                  Phase B      │              Phase C
                                         └─ [VERIFICATION GATE] ─┘
   ── Job Unlock Meter: each completed day unlocks a bucket of live postings ──
```

---

## 2. Job Unlock Meter — quick-win + escalating-value (⭐ APPROVED)

**Mechanic:** completing each sprint day "unlocks" a bucket of the cluster's live job postings, so the demand counter fills up as you progress.

### 2.1 Bucketing algorithm (`demand_intelligence.compute_unlock_assignment`)
On ingest, every job posting in a cluster gets an `unlock_day` (1–14). The distribution is **front-loaded for quick wins and back-loaded with premium value** via quantile bucketing:

1. Compute a composite **value score** `v` per posting in `[0,1]`:
   `v = clamp( 0.45*rate_pct + 0.35*(1 − experience_pct) + 0.20*review_pct )`
   where each `*_pct` is the posting's percentile within the cluster. Higher `v` = easier / better-to-land entry gig.
2. Rank all cluster postings **descending** by `v` (easiest → hardest) and assign them to day buckets by a designed **front-loaded size distribution**:
   `DAY_SIZE_PCT = [12, 11, 10, 9, 8, 8, 7, 6, 6, 5, 5, 4, 4, 5]` (sums to 100)
   Day 1 holds ~12% (the most — an instant quick win), shrinking to ~4–5% on Days 12–14 (the fewest, highest-value premium contracts).
3. **Guarantee:** every day bucket has ≥1 posting (counts floored at 1), Day 1 is the largest bucket, and Day 14 holds only the highest-value postings. Remainder rounding spills to Day 14.

> Note: an earlier per-item power curve (`v**1.8`) proved unreliable because real value scores cluster mid-range. Quantile bucketing guarantees the quick-win + escalating shape deterministically.

**Net effect (example, 450-job cluster):**
| Day | unlocked this day | cumulative | vibe |
|-----|------------------|------------|------|
| 1 | ~46 | 46 | instant win |
| 2 | ~38 | 84 | quick win |
| … | … | … | steady ramp |
| 12–14 | ~8–12 each | 450 | premium contracts |

### 2.2 Recompute & uptick (`unlock_engine`)
On **day completion**, `unlock_engine` computes `unlocked = COUNT(job_feed WHERE cluster_key = <sprint> AND unlock_day <= completed_days)` and writes a `sprint_unlock_snapshots` row, returning `{ newly_unlocked, total_unlocked, total_in_cluster }` for the celebratory UI:
> "🎉 Day 6 complete! +42 postings unlocked → **232 of 450** active jobs now open to you."

### 2.3 Anti–valley-of-despair
The meter is deliberately strongest across Days 8–14 (Phase B/C), where learner drop-off peaks: each completed day visibly closes the distance to the full cluster and the payoff. It reuses the momentum sidebar so confidence, streak, and unlocked-jobs render as one "progress" cluster.

---

## 3. Goals & Non-Goals

### Goals
- **Sprint-first curriculum:** a 14-day sprint derived from a *live job cluster*, not a generic syllabus.
- **Job Unlock Meter:** per-day unlock + escalating-value bucketing (§2).
- **Demand-Validated badges:** profile badges with a live, recomputed "N active jobs" counter.
- **Fulfillment, not just skills:** Phase B enforces deadline + constraints on a real anonymized brief.
- **Proposals as first-class artifacts:** Phase C generates job-specific hooks + a 5-proposal challenge.
- **Iterative adaptation:** no interviews → diagnose (price/portfolio/niche) → assign a 2-hour remedial micro-course.
- **AI mentorship grounded in the job post:** Socratic, job-terminology answers.
- **Parallel-track safety:** all v1 curriculum/dashboard/pipeline code untouched.

### Non-Goals (v2 MVP)
- ❌ Live Upwork/Fiverr scraping at scale — v2 uses a **curated job feed + heuristic scoring** (v1 stance). Live counters are seeded from the feed, not a live API.
- ❌ Auto-submitting proposals to third-party platforms — always human copy-paste + tracking.
- ❌ Multi-language sprints, mobile apps, real-time community/chat.
- ❌ Replacing the v1 30-day deep-dive curricula.

---

## 4. Tech stack (unchanged from v1)

Flask app-factory monolith · Supabase (Postgres + Auth) · `httpx` · Stripe · `edge-tts` · Remotion (local) · LLM fallback chain (`_call_llm`) · Render free tier · Jinja2 + Tailwind CDN + vanilla JS. No new infra.

---

## 5. System context (delta)

Adds a `sprints` blueprint and three service groups that **layer on top of** existing v1 services (curriculum_generator, nudge_engine, supabase_client, llm_config). The Job Unlock Meter is the only new user-facing "stateful" feature; everything else reuses v1 tables/patterns.

```
Browser (new views: sprint dashboard, day, contract, proposals, mentor, badges)
   │ HTTPS
   ▼
Flask app — existing 13 blueprints + NEW `sprints` blueprint
   │
   ├─ Demand Intelligence (new): job_feed ingest → clustering → unlock_day bucketing
   ├─ Sprint Engines (new): sprint_planner · copywork · mock_contract · proposal
   │                       · mentor · verification · iteration
   └─ Unlock Engine (new): meter recompute on day-completion
   │
   ▼
Supabase — v1 schema (untouched) + schema_v2.sql tables
```

---

## 6. Data model additions — see `schema_v2.sql`

| Table | Purpose |
|-------|---------|
| `job_feed` | Curated/normalized postings: title, source, url, description, skills[], rate, posted_at, status, **`unlock_day`**, `cluster_key` |
| `job_clusters` | Skill groups: `cluster_key`, `job_count`, `avg_rate`, `growth_score`, `keywords[]` |
| `demand_snapshots` | Time-series of cluster job_count → live-counter history |
| `sprints` | Topic + cluster + cohort: `phase`, `current_day`, `start/end`, `status` |
| `sprint_days` | 14 rows/sprint: `phase`, `day_no`, `title`, `action_type`, `action_payload` |
| `copywork_projects` | Phase-A replication targets (3) + gap-fill topic |
| `capstone_briefs` | Phase-B anonymized real job post + acceptance criteria |
| `proposals` | Phase-C artifacts: `job_feed_id`, template, hooks[], status, score |
| `badges` | Demand-Validated badges with `jobs_at_issue` |
| `sprint_unlock_snapshots` | Meter state: completed_days, unlocked_count, last_delta |
| `verification_reviews` | Phase-B gate pass/fail + feedback |
| `mentor_sessions` | Chat history scoped to a job description |

**Relationships:** `sprints.cluster_key → job_clusters.cluster_key` · `job_feed.cluster_key → job_clusters.cluster_key` · `capstone_briefs.job_feed_id → job_feed.id` · `proposals.job_feed_id → job_feed.id` · `sprints.badge_id → badges.id`.

---

## 7. Core flows

### 7.1 Enroll → sprint plan (async)
```
Landing (sprint-framed) → Signup → Topic picker (badges visible)
  → POST /sprints/new {topic}
    → demand_intelligence.resolve(topic) → job_cluster
    → sprint_planner: write sprints + 14 sprint_days (background thread, DB-backed log)
  → Dashboard: "Day 1 · Phase A — Copy-Work" + meter
```

### 7.2 Phase A — Copy-Work (Days 1–5)
Days 1–4: `copywork_engine` serves 3 curated replication projects ("rebuild this flow from scratch"). Day 5: gap-fill micro-lesson on the detected missing nuance. Completes when all 3 + gap-fill are done.

### 7.3 Phase B — Mock Contract (Days 6–10)
Day 6: anonymized real brief with hard deadline/constraints. Days 7–8: execute like a paid contract. Days 9–10: write Problem/Solution/Result case study (doubles as first proposal draft). **Verification gate:** `verification_service` (auto-test for code, peer-review for design/copy) → unlocks Phase C.

### 7.4 Phase C — Supply Chain (Days 11–14)
Day 11: `proposal_engine` builds templates + "I see you need X…" hooks. Days 12–13: First-Bid challenge (5 live proposals, `proposals` + `freelance_pipeline.proposals_sent`). Day 14: `iteration_engine` diagnoses stalls → remedial micro-course.

### 7.5 Job Unlock Meter (every day, §2)
Day completion → `unlock_engine` recompute → uptick UI.

### 7.6 Demand-Validated badge
Badge issued when sprint completes **and** Mock Contract passed verification. Profile shows live counter. Clients can filter by `badge: <cluster> within 30 days`.

### 7.7 AI mentorship
`mentor_agent` = RAG over (job description + lesson + progress), Socratic, job-terminology, never the answer outright.

---

## 8. New services (`services/`)

| Service | Responsibility |
|---------|----------------|
| `demand_intelligence.py` | Feed ingest, normalize, cluster, score, `unlock_day` bucketing (§2.1), live counters |
| `unlock_engine.py` | Meter recompute on day-completion + snapshot write |
| `sprint_planner.py` | 14-day plan generation (async, DB-backed) |
| `copywork_engine.py` | Select/sequence the 3 replication projects + gap-fill detection |
| `mock_contract_engine.py` | Match anonymized brief + enforce deadline/constraints |
| `proposal_engine.py` | Proposal templates + job hooks + completeness scoring |
| `mentor_agent.py` | Job-grounded Socratic chat |
| `verification_service.py` | Phase-B gate (auto/peer) + review feedback |
| `iteration_engine.py` | No-interview diagnosis → remedial micro-course |
| `badge_engine.py` | Demand-Validated badge issuance + live counters |

All new LLM work reuses `_call_llm` / `llm_config`; long jobs reuse the DB-backed async + polling pattern from `generate_api`.

---

## 9. New routes (`routes/sprints.py` — one blueprint)

| Route | Purpose |
|-------|---------|
| `POST /sprints/new` | Enroll → spawn plan generation |
| `GET /sprints/<id>` | Sprint dashboard: phases, meter, today's card |
| `GET /sprints/<id>/day/<n>` | Phase-specific day (copywork / contract / proposal) |
| `POST /sprints/<id>/day/<n>/complete` | Complete a day → unlock_engine uptick |
| `GET /sprints/<id>/contract` | Mock Contract brief + submit |
| `POST /sprints/<id>/contract/submit` | Deliverable → verification gate |
| `GET /sprints/<id>/proposals` | Proposal builder + First-Bid tracker |
| `POST /sprints/<id>/proposals/<pid>/submit` | Mark a proposal submitted |
| `GET /mentor` / `POST /mentor/turn` | AI mentorship |
| `GET /sprints/<id>/badge` | Demand-Validated badge |

Blueprint registration is additive in `app.py` (no v1 changes).

---

## 10. BDD — behavior-driven spec

Gherkin features live in [`tests/features/sprint/`](../../tests/features/sprint/) and run under the existing `behave` harness (`tests/environment.py`). They cover the meter, the three phases, the verification gate, and the badge. **The meter is treated as a first-class, testable behavior** — not just a UI flourish.

---

## 11. Build order

| # | Deliverable | Depends |
|---|-------------|---------|
| 1 | `schema_v2.sql` | — |
| 2 | `demand_intelligence.py` + seed feed | 1 |
| 3 | `sprints.py` blueprint + dashboard/day + `sprint_planner.py` | 1,2 |
| 4 | **`unlock_engine.py` + Job Unlock Meter (dashboard + day uptick)** | 3 |
| 5 | Phase B: `mock_contract_engine.py` + `verification_service.py` | 3 |
| 6 | Phase C: `proposal_engine.py` + `iteration_engine.py` | 5 |
| 7 | `badge_engine.py` + profile badges | 2,5 |
| 8 | `mentor_agent.py` | 1,3 |
| 9 | BDD features green under `behave` | 2–8 |

---

## 12. Cost, security, resilience

| Concern | Approach |
|---------|----------|
| Cost | ~$0–15/mo. Free LLM models; curated feed (no scraping infra); peer review for design/copy |
| RLS | service-role for MVP (v1 stance); badge + job counters are **public read** pre-launch (the marketing hook) |
| Badge integrity | Valid only if `verification_reviews.status = pass` AND sprint completed |
| Anonymization | `capstone_briefs` stores only `job_feed_id` ref, never client PII |
| Proposal safety | Never auto-submit; human copy-paste + tracking |
| Async survival | DB-backed progress log; gunicorn 2-worker caveat applies (v1 pattern) |
| Parallel-track safety | No v1 table/route/service modified; all additions are additive |

---

*References: `research_material.txt`, `schema_v2.sql`, `tests/features/sprint/*.feature`, v1 `engineering-spec.md` + `architecture.md`.*
