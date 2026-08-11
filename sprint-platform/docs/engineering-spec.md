# FreelanceLaunch · Sprint Platform — Engineering Spec (v1)

**Status:** New project · **Version:** 1.0 · **Date:** 2026-08-11 · **Owner:** Dhruba
**Product truth:** [`./mockups/product-mockup.html`](./mockups/product-mockup.html) — an 8-screen static walkthrough. This spec is the mockup rendered as behavior.
**Branch:** `sprint-platform` · **DB:** [`../db/schema.sql`](../db/schema.sql)
**Companions:** [`architecture.md`](./architecture.md) · [`bdd/`](./bdd/) · [`decisions.md`](./decisions.md)

---

## 1. Product thesis (one paragraph)

FreelanceLaunch is a **14-day, cohort-batched, demand-validated sprint** that compresses *teach → fulfill → sell* into a single loop and uses **live demand data as the psychological engine**. Learners don't watch a generic course; they rebuild real projects (Copy-Work), fulfill a real anonymized brief like it's paid (Mock Contract), and send 5 live proposals (Supply Chain). The product's moat is the **client loop**: a Demand-Validated badge carries a live "N jobs open right now" counter, is only issued after the Mock Contract passes verification, and lets clients **filter freelancers by "Completed [Skill] Sprint within the last 30 days."**

---

## 2. Goals & Non-Goals

### Goals
- **Sprint-first product:** every skill ships a 14-day sprint built from a live job cluster — no generic syllabus.
- **Job Unlock Meter (⭐):** completing each day unlocks a bucket of the cluster's live job postings; every completion produces a celebratory "+N postings" uptick.
- **Fulfillment, not just skills:** Phase B forces deadline-and-constraint execution of a real anonymized brief; the case study doubles as the first proposal draft.
- **Two verification gates:** Phase A → B (copy-work rubric auto-check) and Phase B → C (mock-contract verification). Locks make the badge credible.
- **Client-facing profile:** public demand-validated badges with live counters + trend; clients filter by skill + recency.
- **Proposals as first-class artifacts:** engineered "I see you need X…" hooks + a 5-proposal First-Bid challenge. Human-initiated submission only.
- **Outcome tracking on the sprint:** responses → interviews → offers → contracts → earnings → repeat clients all live on the sprint record (no separate pipeline).
- **AI mentorship grounded in the job post:** Socratic, uses the target job's exact terminology, never hands over the answer.
- **Cohort framing + per-user pacing:** "Cohort #12 · ends Aug 23" with each user's own day counter inside the cohort window.
- **Momentum widget:** day streak, confidence, proposals sent, contracts — one progress cluster with nudges.

### Non-Goals (v1)
- ❌ Live Upwork/Fiverr/Contra scraping at scale. v1 uses a **curated job feed + heuristic scoring**; live counters are seeded from the feed, not a live API (mockup: "we curate the live demand feed before we build it").
- ❌ Auto-submitting proposals to third-party platforms. Always human copy-paste + confirm + track.
- ❌ Multi-language, mobile apps, real-time chat/community, peer-review marketplace at scale.
- ❌ The v1 30-day "deep-dive" curriculum and the old `freelance_pipeline` table — removed by design in this new project.

---

## 3. User journeys (one per mockup screen)

### J1 · Landing (`/`)
- Static marketing page: hero, demand counter card (450 jobs / $62/hr / +18%), 3-phase explainer, CTA band for the Demand-Validated badge.
- Nav: Sprints, Topics, How it works, Pricing, Start free.
- The headline demand counter is the marketing hook — it must render without auth and read from `job_clusters`.

### J2 · Sprint Picker (`/sprints`)
- Lists demand-validated sprints as cards: icon, name, keywords, **live badges** ("● 450 jobs open", "$62/hr avg", "14 days"), one-line outcome promise, Start sprint CTA, trending flag.
- "Request a sprint" — curated-feed intake for a skill not yet offered (creates a `job_clusters` row in `requested` status).
- **Acceptance:** no sprint card shows a stale counter; all numbers come from `job_clusters`/`demand_snapshots`.

### J3 · Sprint Dashboard (`/sprints/<id>`)
- Header: sprint title + "Day N · Phase X" badge; cohort line ("Cohort #12 · ends Aug 23").
- **Phase lock track:** 3 phase cards. Phase A active (n/5 days); Phase B **locked until Phase A passes verification**; Phase C **locked until the Mock Contract passes verification**.
- **Job Unlock Meter:** `unlocked / total` ("186 / 450 active jobs unlocked") + "+38 postings unlocked so far" chip + 14-bar track.
- **Today card:** Watch lesson (✓), Replicate the project, Self-check vs rubric → "Open Day N →".
- **Momentum card:** Day streak 🔥, Confidence n/100, Proposals sent, Contracts, plus a Nudge message.
- Routes: `GET /sprints/<id>` and phase/day helpers; all state gated by ownership.

### J4 · Day View (`/sprints/<id>/day/<n>`) — Phase A example
- Day header: "Phase A · Day 4 · Copy-Work · Project 2 — Rebuild the Abandoned-Cart Flow".
- **Day-complete uptick banner:** shown after completing the day: "🎉 Day 4 complete — +38 postings → 186 of 450 active jobs open to you."
- **Watch · Lesson:** TwoPanel HTML preview (kinetic text + TTS). No MP4 required in-request; MP4 is a later YouTube-distribution concern.
- **Copy-Work Task:** trigger / sequence / dynamic block / coupon steps; "Replicate from scratch"; "Pass 3-point rubric" (auto-checked).
- **Gap-Fill preview card:** auto-detected nuance from the previous project ("mobile responsiveness") → "Day 5 serves a targeted 30-min micro-lesson."
- Every Phase A/C/B day renders the correct phase-specific action from `sprint_days.action_type`.

### J5 · Mock Contract (`/sprints/<id>/contract`) — Phase B
- "Your First 'Client' — fulfill it like it's paid." Brief card: anonymized real job post, **Due in N days** badge.
- Requirements + Constraints (deadline, budget, client notes).
- Steps: execute flow (Days 6–8) → write Problem/Solution/Result case study (Days 9–10).
- **Verification Gate:** "locks Phase C" — automated flow check + case study written. Submission via `POST /sprints/<id>/contract/submit`; result written to `verification_reviews (gate='B')`.
- **Anonymization requirement:** `capstone_briefs` stores only `job_feed_id`, never client identity/PII.

### J6 · Proposal Builder (`/sprints/<id>/proposals`) — Phase C
- **First-Bid Challenge:** 0/5 progress bar + table of live jobs (rate + status: Draft / Not started).
- Proposal Builder card: **Opening hook** ("I see you need a Klaviyo flow that recovers abandoned carts — I just rebuilt exactly that flow…"), **Proof (from your Mock Contract)**, **CTA**.
- Actions: Copy proposal / Edit. Submission is human-initiated: copy → paste on the platform → confirm → `status='submitted'`, `sprints.proposals_sent += 1`, record `platform`.
- "We never auto-submit" — enforced in the UI copy and the API.

### J7 · Demand Profile (`/profile/<user>`, public) — the client loop
- Public freelancer profile: name, headline ("Freelancer · Email Automation & Web Scraping").
- **Demand-Validated Badges:** each shows cluster, **"● N active jobs right now"** with trend ("↑ from 410 two weeks ago"), and verification provenance ("Mock contract verified · 5 proposals sent · 1 interview").
- Case Study Portfolio: Problem/Solution/Result artifacts (client-format).
- **Client filter:** a search surface that returns freelancers by `badge: <cluster> within 30 days`, powered by the `public_freelancers` view.
- **Badge integrity:** a badge is issued only when the Mock Contract passed verification **and** the sprint completed — never for "finishing a course."

### J8 · AI Mentor (`/mentor`)
- Chat UI grounded in: the user's live target job description + their progress + their sprint.
- Mentor replies are Socratic, use the job's exact terminology, and **never hand over the finished answer**.
- Context chip: "📌 Context: job #1042 · Klaviyo · checkout recovery · progress 60%".
- Backend: request-scoped RAG over (job description + lesson content + progress), LLM fallback chain, 20s timeout with a graceful "thinking…" fallback.

---

## 4. Core mechanics (cross-cutting)

### 4.1 Job Unlock Meter (⭐)
1. **Bucketing (ingest):** on feed ingest, each posting gets an `unlock_day` (1–14) by quantile: composite value `v = clamp(0.45·rate_pct + 0.35·(1−experience_pct) + 0.20·review_pct)`, rank descending (easiest→hardest), assign by `DAY_SIZE_PCT = [12,11,10,9,8,8,7,6,6,5,5,4,4,5]`. Day 1 is the largest bucket (quick win); Day 14 holds the highest-value postings. Every bucket has ≥1.
2. **Recompute (day completion):** `unlocked = COUNT(job_feed WHERE cluster_key=<sprint> AND unlock_day <= completed_days)`; write a `sprint_unlock_snapshots` row; return `{newly, total, cluster}`.
3. **Uptick UI:** the day-complete toast and dashboard meter celebrate the delta.
4. **Anti-valley-of-despair:** meter is deliberately strongest across Days 8–14 (Phase B/C) where drop-off peaks.
5. **Bid-access, not auto-bid:** the meter governs *visibility* into the feed; actual proposal submission stays human-initiated and gated by verification.

### 4.2 Two verification gates
- **Gate A (Phase A→B):** Phase B unlocks only when `verification_reviews (sprint, gate='A') = pass` — the 3 copy-work rubrics + gap-fill are auto-checked (code) or peer-checked (design/copy).
- **Gate B (Phase B→C):** Phase C (job feed + proposals) unlocks only when `verification_reviews (sprint, gate='B') = pass` — the Mock Contract deliverable passes auto/peer review.
- A lock never silently breaks: if a gate is required but absent, the UI shows the lock + the missing item.

### 4.3 Outcome tracking (sprint-owned)
- `sprints` carries `proposals_sent, responses_received, interviews_held, offers_received, contracts_won, contracts_completed, total_earned, avg_contract_value, first_contract_at, repeat_clients, is_actively_seeking`.
- Writes come from: proposal submit (+1 proposals_sent), the proposal iteration loop (responses/interviews), and `contracts` add/complete.
- The **iteration loop** (Day 14): if `proposals_sent ≥ 5` and `responses_received = 0`, `iteration_engine` diagnoses the bottleneck (price / portfolio / niche) from the sprint's own data and assigns a 2-hour remedial micro-course.

### 4.4 Momentum
- `user_momentum.day_streak` increments per completed day; `confidence` is recomputed by the nudge engine on every progress mark; the Momentum card renders streak · confidence · proposals · contracts.
- Nudge messages are rule-based + LLM-assisted, scoped to where the user is in the sprint.

### 4.5 Demand intelligence
- `demand_intelligence` ingests the curated feed, normalizes postings, clusters by skill, scores clusters (count, rate, growth, keywords), assigns `unlock_day`, caches live counters in `job_clusters`, and snapshots time-series into `demand_snapshots` (powers "↑ from 410").
- A nightly refresh recomputes counters; the UI reads `job_clusters` (O(1)), never a live query.

---

## 5. LLM & async strategy
- **All LLM work reuses one fallback chain** (`_call_llm`): OpenRouter free → env config → Omniroute local → Hermes → deterministic fallback. No new provider logic.
- **Sprint plan generation is async**: background thread, DB-backed progress log, frontend polling (same pattern as v1 `generate_api`).
- **Mentor** is request-scoped and short (2–4s); 20s timeout + graceful fallback.
- **Gap-Fill detection** (Phase A) runs once per copy-work completion: flags the missing nuance from rubric results.
- **Proposal generation** reuses the LLM for hooks but must have a deterministic template fallback (offline-safe).

---

## 6. Security, privacy, cost
| Concern | Approach |
|---------|----------|
| **RLS** | service-role for MVP; **badge + job counters are public read** pre-launch (the marketing hook) |
| **Badge integrity** | badge valid only if `verification_reviews(gate='B') = pass` AND sprint `status='completed'` |
| **Anonymization** | `capstone_briefs` stores only `job_feed_id`; never client PII |
| **Proposal safety** | never auto-submit to third parties; always human copy-paste + confirm + track |
| **Ownership** | all `/sprints/*` state changes are gated to the sprint owner |
| **Async survival** | DB-backed progress log; multi-worker caveat applies (DB is source of truth) |
| **Cost** | ~$0–15/mo: free LLM models, curated feed (no scraping infra), local HTML previews, peer review for design/copy |

---

## 7. Open decisions for the build phase
1. **Client search surface** (J7 filter): dedicated route (`/clients/freelancers?cluster=&within_days=30`) vs. a section inside the public profile. Recommend the dedicated route + the `public_freelancers` view.
2. **Cohort creation**: manual (admin creates cohorts) vs. auto-open cohorts on a cadence. Recommend manual for v1.
3. **Payments**: nav shows "Pricing" but no tiers in the mockup. Recommend deferring monetization decisions to a pricing spec, keeping the schema payment-ready (`user_profiles.tier` not yet modeled).
4. **MP4/YouTube**: mockup shows HTML previews only. Recommend keeping the overnight Remotion pipeline out of v1 scope; revisit for acquisition later.

---

*References: `./mockups/product-mockup.html` (primary) · `./research_material.txt` (thesis) · superseded: v2 sprint track spec in the v1 repo.*
