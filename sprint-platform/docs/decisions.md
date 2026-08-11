# Product & Architecture Decisions

Record of the decisions that shaped this new project. Source of truth: `../../mockups/product-mockup.html`.

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| D1 | Scope | **Sprint-only product.** No v1 30-day curriculum, no `freelance_pipeline`. | The mockup shows only sprints; the sprint owns the outcome lifecycle. A "completely new project" justifies the clean cut. |
| D2 | Pacing | **Cohort-batched with per-user pacing.** Cohort has start/end; each user keeps their own `current_day`. | Mockup dashboard: "Cohort #12 · ends Aug 23". |
| D3 | Demand data | **Curated feed + nightly heuristic refresh.** No live scraping infra. | Mockup: "we curate the live demand feed before we build it". Free-tier economics. |
| D4 | Client loop | **Public profile + badge filter is v1.0 scope**, not post-MVP. | Mockup screen 7 is a product screen; it's the moat (partner-with-hiring-side). |
| D5 | Stack | **Flask + Supabase + Jinja2 + Tailwind**, fresh codebase, LLM fallback chain retained. | Proven, $0–15/mo per `cost-efficiency-analysis.md`. |
| D6 | Gates | **Two verification gates**: A→B (copy-work rubric) and B→C (mock contract). | Mockup shows both: "Unlocks when Phase A passes verification" and the "Verification Gate locks Phase C". |
| D7 | Outcomes | Proposal/response/interview/contract/earnings counters **live on `sprints`**. | Removes the redundant `freelance_pipeline`; the sprint is the single record. |
| D8 | Videos | **HTML TwoPanel + TTS previews only** in v1. Remotion/YouTube deferred. | Mockup day view: "TwoPanel HTML preview — kinetic text + TTS (no MP4)". |

## Superseded docs
- `web-app/docs/sprint/engineering-spec.md` + `web-app/docs/sprint/architecture.md` (v2 sprint track) — superseded by this project's specs.
- `web-app/docs/engineering-spec.md` / `architecture.md` (v1) — the v1 product is out of scope for the sprint platform.
- `web-app/schema.sql` / `schema_v2.sql` — replaced by `db/schema.sql`.

## Carry-over principles (unchanged from v1)
- Free-tier economics · No-500 philosophy · Async generation · LLM fallback chain · Single deployable monolith · Public counters as marketing surface.
