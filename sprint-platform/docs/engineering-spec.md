# FreelanceLaunch · Sprint Platform — Engineering Spec (v1)

**Status:** New project · **Version:** 1.1 · **Date:** 2026-08-16 · **Owner:** Dhruba
**Product truth:** [`./mockups/product-mockup.html`](./mockups/product-mockup.html) — an 8-screen static walkthrough. This spec is the mockup rendered as behavior.
**Branch:** `sprint-platform` · **DB:** [`../db/schema.sql`](../db/schema.sql)
**Companions:** [`architecture.md`](./architecture.md) · [`api.md`](./api.md) · [`bdd/`](./bdd/) · [`decisions.md`](./decisions.md)

> **v1.1 (2026-08-16):** synced to the implemented codebase — async content generation with
> DB-backed progress polling, auto-open cohorts, Gate A/B auto-checks, proposal outcome
> logging, contract roll-ups, case-study write path, and admin demand refresh. See
> [`api.md`](./api.md) for the endpoint reference.

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
- **Content generation progress:** the 14 day-lessons generate async after enrollment; the dashboard polls `GET /sprints/<id>/generation` (`{status, generated, total}`) and hides the spinner at `ready` (eng-spec §5).
- **Contracts & Earnings card:** lists recorded contracts (won/completed) with an add-contract form → `POST /sprints/<id>/contract/add`.
- **Complete sprint button:** explicit `POST /sprints/<id>/complete` (also fired by finishing Day 14).
- Routes: `GET /sprints/<id>`, `GET /sprints/<id>/generation`, day/complete/copywork helpers; all state gated by ownership.

### J4 · Day View (`/sprints/<id>/day/<n>`) — Phase A example
- Day header: "Phase A · Day 4 · Copy-Work · Project 2 — Rebuild the Abandoned-Cart Flow".
- **Day-complete uptick banner:** shown after completing the day: "🎉 Day 4 complete — +38 postings → 186 of 450 active jobs open to you."
- **Watch · Lesson:** TwoPanel JS player — a pre-built Remotion composition (`static/video/lesson-player.js`) with kinetic text + edge-tts voiceover, played in-browser (no MP4; YouTube distribution is a later concern). The lesson script + key points are generated per day from the cluster's live job posting (`lesson_engine.lesson_for_day`, LLM with a deterministic job-grounded fallback) and stored in `sprint_days.action_payload.lesson`; the async content worker also generates the voiceover (`video_engine` → edge-tts → `voiceovers` Storage bucket) and stores `lesson.voiceover = {url, duration_seconds}`. When no voiceover exists yet, the day view renders the kinetic-text fallback (No-500).
- **Copy-Work Task:** trigger / sequence / dynamic block / coupon steps rendered from the project's generated `clone_steps`; "Replicate from scratch"; "Pass 3-point rubric" (auto-checked) rendered from the project's generated `rubric`. Submission requires a **valid http(s) link to the rebuilt flow** — an empty or scheme-less URL is rejected and never marks the project done.
- **Gap-Fill preview card:** auto-detected nuance from the previous project ("mobile responsiveness", carried on copy-work project 2's `gap_fill_topic`) → "Day 5 serves a targeted 30-min micro-lesson."
- Every Phase A/C/B day renders the correct phase-specific action from `sprint_days.action_type`.

### J5 · Mock Contract (`/sprints/<id>/contract`) — Phase B
- "Your First 'Client' — fulfill it like it's paid." Brief card: anonymized real job post, **Due in N days** badge.
- Requirements + Constraints (deadline, budget, client notes).
- Steps: execute flow (Days 6–8) → write Problem/Solution/Result case study (Days 9–10).
- **Verification Gate:** "locks Phase C" — automated flow check + case study written. Submission via `POST /sprints/<id>/contract/submit`; result written to `verification_reviews (gate='B')`.
- **Gate B auto-check:** a **valid** deliverable URL (http/https) on the review row **plus a saved case study** → `verification_service.auto_check_gate_b` writes the pass row inline — Phase C unlocks immediately (arch §7 inline auto-test).
- **Case study (Days 9–10):** `POST /sprints/<id>/case-study` upserts the Problem/Solution/Result write-up; it is stored with `is_draft = not gate_b_passed` — drafts stay internal, and once Gate B passes (a re-save with the pass in place) it is the public profile portfolio item.
- **Anonymization requirement:** `capstone_briefs` stores only `job_feed_id`, never client identity/PII. The brief is synthesized from the cluster's first active posting (`mock_contract_engine.synthesize`), with a No-500 in-memory default when the feed is empty.

### J6 · Proposal Builder (`/sprints/<id>/proposals`) — Phase C
- **First-Bid Challenge:** 0/5 progress bar + table of live jobs (rate + status: Draft / Not started).
- Proposal Builder card: **Opening hook** ("I see you need a Klaviyo flow that recovers abandoned carts — I just rebuilt exactly that flow…"), **Proof (from your Mock Contract)**, **CTA**.
- Actions: Copy proposal / Edit. Submission is human-initiated: copy → paste on the platform → confirm → `status='submitted'`, `sprints.proposals_sent += 1`, record `platform`. Submission on an unverified platform is rejected.
- "We never auto-submit" — enforced in the UI copy and the API.
- **Outcome logging:** `POST /sprints/<id>/proposals/<pid>/respond` with `outcome=response|interview|offer` bumps `responses_received` / `interviews_held` / `offers_received` on the sprint.
- **Iteration diagnosis:** rendered on this page when `proposals_sent ≥ 5` and `responses_received = 0` — `iteration_engine.diagnose` names the bottleneck (price / portfolio / niche) from the sprint's own data.

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
  - **Auto-check trigger:** every `POST /sprints/<id>/day/<n>/copywork` requires a **valid http(s) rubric URL**; it marks that day's copy-work project done (storing the URL as `submitted_url` evidence) and runs `auto_check_gate_a` — all 3 projects done **and each with a valid submitted URL** → pass → Phase B unlocks.
- **Gate B (Phase B→C):** Phase C (job feed + proposals) unlocks only when `verification_reviews (sprint, gate='B') = pass` — the Mock Contract deliverable passes auto/peer review.
  - **Auto-check trigger:** `POST /sprints/<id>/contract/submit` with a **valid** deliverable URL (http/https) **and a saved case study** → `auto_check_gate_b` writes the pass row inline.
- A lock never silently breaks: if a gate is required but absent, the UI shows the lock + the missing item.

### 4.3 Outcome tracking (sprint-owned)
- `sprints` carries `proposals_sent, responses_received, interviews_held, offers_received, contracts_won, contracts_completed, total_earned, avg_contract_value, first_contract_at, repeat_clients, is_actively_seeking`.
- Writes come from: proposal submit (+1 `proposals_sent`), `POST .../proposals/<pid>/respond` (+1 response/interview/offer counter), and `POST .../contract/add` + `POST .../contract/<id>/complete` (contracts, earnings, completion count).
- The **iteration loop**: when `proposals_sent ≥ 5` and `responses_received = 0`, `iteration_engine.diagnose` names the bottleneck (price / portfolio / niche) from the sprint's own data; the diagnosis + remedial micro-course assignment render on the proposals page (no separate Day-14 step).

### 4.4 Momentum
- `user_momentum.day_streak` increments per completed day; `confidence` is recomputed by the nudge engine on every progress mark; the Momentum card renders streak · confidence · proposals · contracts.
- Nudge messages are rule-based + LLM-assisted, scoped to where the user is in the sprint.

### 4.5 Demand intelligence
- `demand_intelligence` ingests the curated feed, normalizes postings, clusters by skill, scores clusters (count, rate, growth, keywords), assigns `unlock_day` (`assign_unlock_days`, quantile buckets), caches live counters in `job_clusters`, and snapshots time-series into `demand_snapshots` (powers "↑ from 410").
- Refresh is an **explicit action** — admin `POST /admin/clusters/<cluster_key>/refresh` runs `assign_unlock_days` + `refresh_cluster(snapshot=True)` (writes a `demand_snapshots` row), or a nightly cron calls the same helpers. Never an implicit read; the UI reads `job_clusters` (O(1)), never a live query.
- Profile badges read the latest snapshot per cluster for the trend line (`demand_snapshots`), falling back to the `jobs_at_issue` stamped on the badge.

---

## 5. LLM & async strategy
- **All LLM work reuses one fallback chain** — `services/llm.py call_llm`: env-configured endpoint (`LLM_API_URL`/`LLM_API_KEY`/`LLM_MODEL`) → OpenRouter (`OPENROUTER_API_KEY`) → Omniroute local (`127.0.0.1:20128`, socket probe) → `None` → deterministic fallback. No new provider logic; every step is try/except with short timeouts.
- **Sprint plan generation is async (implemented):** at enrollment the skeleton writes synchronously (`sprint_planner.create_plan` → 14 `sprint_days`; `copywork_engine.create_projects` → 3 projects) so the request never waits; `lesson_engine.generate_sprint_content` then fills lesson + project-anatomy payloads on a **background thread**. The count of populated `action_payload.lesson` values IS the DB-backed progress log; the dashboard polls `GET /sprints/<id>/generation` (`{status, generated, total}`) and the spinner hides at `ready`.
- **Mentor** is request-scoped and short (2–4s); it tries `call_llm`, requires the answer to echo the job's terminology (`_grounded`), and falls back to a deterministic guided template that never hands over the finished answer.
- **Gap-Fill detection** (Phase A) is deterministic in v1 — the missing nuance lives on copy-work project 2's `gap_fill_topic` and surfaces on the day view before Day 5.
- **Proposal generation** reuses the LLM for hooks but has a deterministic template fallback (offline-safe).

---

## 6. Security, privacy, cost
| Concern | Approach |
|---------|----------|
| **RLS** | service-role for MVP; **badge + job counters are public read** pre-launch (the marketing hook) |
| **Auth** | session cookie `user_id` must reference a real `auth.users` UUID; malformed ids are dropped before any uuid-FK write (22P02 guard), and login refuses non-existent emails |
| **Badge integrity** | badge valid only if `verification_reviews(gate='B') = pass` AND sprint `status='completed'` |
| **Anonymization** | `capstone_briefs` stores only `job_feed_id`; never client PII |
| **Proposal safety** | never auto-submit to third parties; always human copy-paste + confirm + track |
| **Ownership** | all `/sprints/*` state changes are gated to the sprint owner |
| **Async survival** | DB-backed progress log; multi-worker caveat applies (DB is source of truth) |
| **Cost** | ~$0–15/mo: free LLM models, curated feed (no scraping infra), local HTML previews, peer review for design/copy |

---

## 7. Open decisions for the build phase
1. ✅ **Resolved:** client search surface — dedicated route `GET /clients/freelancers?cluster=&within_days=` powered by the `public_freelancers` view (live DB, `routes/clients.py`).
2. ✅ **Resolved:** cohort creation — **auto-open on enrollment**: the learner joins the latest active cohort for the cluster, or a new `Cohort #N` (14-day window) is opened for them (`routes/main.py _open_cohort`); admins can still create cohorts manually.
3. **Payments**: nav shows "Pricing" but no tiers in the mockup. Recommend deferring monetization decisions to a pricing spec, keeping the schema payment-ready (`user_profiles.tier` not yet modeled).
4. **YouTube distribution**: the two-panel lesson is a JS Remotion Player composition in v1 (no MP4 render). Rendering distributable MP4s for YouTube stays out of v1; revisit for acquisition later.

---

*References: `./mockups/product-mockup.html` (primary) · `./research_material.txt` (thesis) · superseded: v2 sprint track spec in the v1 repo.*
