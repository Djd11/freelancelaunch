# Sprint Platform — Project Memory

## What this is
A 14-day, cohort-batched, demand-validated **sprint** product that compresses
teach → fulfill → sell into one loop. Flask app built from
`docs/mockups/product-mockup.html` as the single source of truth.

## Ground truth (read before coding)
- `docs/mockups/product-mockup.html` — product truth (8 screens)
- `docs/engineering-spec.md` — product contract, journeys, mechanics
- `docs/architecture.md` — system design, layers, data flows
- `docs/decisions.md` — D1–D8 decisions + rationale
- `docs/bdd/*.feature` — Gherkin source of truth (port to `tests/features/`)
- `db/schema.sql` — PostgreSQL / Supabase schema (dedicated project, not v1)

## Skills available in this project
Skills live in `.claude/skills/<name>/SKILL.md` and are auto-discovered.

### spec-master — MUST USE before any coding task
Reads + indexes the specs above, cross-references the task against BDD scenarios,
and only writes code that satisfies them. Halts if a task conflicts with
`docs/architecture.md`.

### qa-strategy — MUST USE for bugs / behavior changes / debugging
Test-first: never write a fix without first having a failing test that reproduces
it. This project's test bed is the behave suite (`tests/features/`, FakeSupabase
dev mode — no network).

## How to run the tests
- Full suite: `behave` (or `python3 -m behave`) from repo root (`behave.ini` sets `paths = tests/features/`)
- One feature: `behave tests/features/<name>.feature --no-capture -k`
- Each scenario runs against a fresh in-memory FakeSupabase (`reset_dev_db()` in `tests/environment.py`) — no real DB, no network.

## Conventions
- Spec changes land in `docs/bdd/*.feature` FIRST, then are ported to `tests/features/`.
- Code only ever satisfies the BDD scenarios; if a request conflicts with
  `docs/architecture.md`, halt and ask.
- This project is isolated on branch `sprint-platform` (root commit). Do not pull
  in v1 workspace files (`web-app/`, `venv/`, global skills config).
