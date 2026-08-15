---
name: spec-master
description: >
  MUST USE when starting any implementation or coding task in this project.
  Before answering, reads and indexes docs/architecture.md,
  docs/engineering-spec.md, docs/bdd/*.feature (source of truth) and
  tests/features/*.feature (the behave port), cross-references the request
  against those specs, and only writes code that satisfies the BDD
  scenarios. Halts and asks for clarification if a task conflicts with
  docs/architecture.md.

  NOT for: pure copywriting, research-only questions, or tasks with no code.
---

# Spec Master Skill

## Context Sources
Before answering ANY task, you MUST read and index the following files:
1. `docs/architecture.md` (System Design)
2. `docs/engineering-spec.md` (Product contract + technical requirements)
3. `docs/bdd/*.feature` (Gherkin source of truth, driven from
   `docs/mockups/product-mockup.html`)
4. `tests/features/*.feature` + `tests/steps/` (the behave implementation)
5. `db/schema.sql` (PostgreSQL / Supabase schema)

## Workflow
1. **Ingest**: Read the relevant sections of the above files based on the user's task.
2. **Cross-Reference**: Verify the task request against the BDD scenarios and the
   engineering spec. Spec changes go to `docs/bdd/*.feature` FIRST, then are ported
   to `tests/features/`.
3. **Plan**: Output a plan that explicitly cites which spec section justifies each step.
4. **Execute**: Only write code that satisfies the BDD scenarios.

## Constraint
If a task conflicts with `docs/architecture.md`, halt and ask for clarification before coding.
