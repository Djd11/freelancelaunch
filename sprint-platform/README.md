# FreelanceLaunch · Sprint Platform

A 14-day, cohort-batched, demand-validated **sprint** that compresses *teach → fulfill → sell*
into one loop — built from the product mockup (`./docs/mockups/product-mockup.html`) as the single
source of truth.

## What this is
- **New project on branch `sprint-platform`.** Fresh codebase, no v1 baggage (no `freelance_pipeline`,
  no 30-day curriculum).
- **Product truth:** `./docs/mockups/product-mockup.html` (8 screens: Landing, Sprint Picker, Sprint Dashboard,
  Day, Mock Contract, Proposal Builder, Demand Profile, AI Mentor).
- **Specs** (spec-master + qa-strategy driven):
  - `docs/engineering-spec.md` — product contract, journeys, mechanics
  - `docs/architecture.md` — system design, layers, data flows
  - `docs/decisions.md` — D1–D8 decisions + rationale
  - `docs/bdd/` — 8 Gherkin feature files (the future behave suite)
  - `db/schema.sql` — fresh PostgreSQL/Supabase schema

## Key mechanics (from the mockup)
1. **Job Unlock Meter** — each completed day unlocks a bucket of the cluster's live postings.
2. **Two verification gates** — Phase A→B (copy-work rubric) and Phase B→C (mock contract).
3. **Demand-Validated badges** — issued only on verified completion; public profile + client filter.
4. **Sprint-owned outcomes** — proposals → responses → interviews → contracts → earnings on `sprints`.

## Next steps (build order)
1. Scaffold the Flask app from `docs/architecture.md` (blueprints + services).
2. Port the 8 BDD features into a `behave` suite (live-DB adapter pattern).
3. Implement `db/schema.sql` in Supabase (**a NEW, dedicated project** — see below).
4. Build green screen-by-screen: Landing → Picker → Dashboard → Day → Contract → Proposals → Profile → Mentor.

## Isolation guarantees
### Git — branch
- This project lives **only** on branch `sprint-platform`, which is a **root commit with no parent**
  — it shares no history with anything.
- A root `.gitignore` **allow-lists only `sprint-platform/`**: an accidental `git add .` can never
  sweep the v1 workspace (`web-app/`, `venv/`, old planning docs, skills config) into this branch.
  `git status` here will only ever show `sprint-platform/` as trackable.
- The v1 workspace stays untouched on disk; commit it to its own `master` branch whenever you want
  it versioned.
- Everything this project references is **in-project** (`docs/mockups/product-mockup.html`,
  `docs/research_material.txt`) — no external-file dependencies on the v1 tree.

### Supabase — database
- This schema targets a **new, dedicated Supabase project** — never the v1 database.
  See [`docs/supabase-setup.md`](./docs/supabase-setup.md).
- `db/schema.sql` opens with a **guard that aborts** if v1 tables
  (`topics`, `curricula`, `freelance_pipeline`, …) are detected — protecting the v1 DB
  from accidental application (several table names collide: `cohorts`, `contracts`,
  `sprints`, `proposals`, `job_feed`, `badges`, `mentor`).
- Copy `.env.example` → `.env` with the **new** project's URL + keys. Do not reuse v1 credentials.
