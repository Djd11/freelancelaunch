# FreelanceLaunch · Sprint Platform

A 14-day, cohort-batched, demand-validated **sprint** that compresses *teach → fulfill → sell*
into one loop — built from the product mockup (`../mockups/product-mockup.html`) as the single
source of truth.

## What this is
- **New project on branch `sprint-platform`.** Fresh codebase, no v1 baggage (no `freelance_pipeline`,
  no 30-day curriculum).
- **Product truth:** `../mockups/product-mockup.html` (8 screens: Landing, Sprint Picker, Sprint Dashboard,
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
2. Port the 8 BDD features into a `behave` suite (tests/support FakeSupabase pattern from v1).
3. Implement `db/schema.sql` in Supabase.
4. Build green screen-by-screen: Landing → Picker → Dashboard → Day → Contract → Proposals → Profile → Mentor.
