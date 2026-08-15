---
name: qa-strategy
description: >
  MUST USE for bug fixing, debugging, or any iteration that touches
  existing behavior in this project. Enforces a test-first protocol:
  never write a fix without first writing a failing test that
  reproduces the bug. Use when the user reports a bug, a test failure,
  a regression, or asks to change behavior safely ("fix X", "make X
  work", "why is X broken", "add a test for X").

  This project's test bed is the behave suite in tests/features/
  (live Supabase test project via tests/live_db_adapter.py). A fix that
  has no failing feature or unit test does not exist.

  NOT for: greenfield features with no existing behavior, pure
  copywriting, or exploratory research.
---

# QA Strategy

## Role
You are a Senior Software Architect focused on bug-free iterations.

## Test-First Constraint
NEVER write a fix without first having a failing test that reproduces the bug.

## This project's test bed
- Behave suite: `tests/features/*.feature` (BDD source of truth lives in `docs/bdd/`).
- Run suite: `behave` (or `python3 -m behave`) from the repo root — `behave.ini` sets
  `paths = tests/features/`.
- Run one feature: `behave tests/features/<name>.feature --no-capture -k`.
- Live Supabase: every scenario runs against the dedicated test project via
  `tests/live_db_adapter.py` (readable fixture IDs → real UUIDs, per-scenario
  cleanup in `tests/environment.py`). There is no in-memory database.

## Process
1. **Reproduce**: Run the existing suite, or write the smallest failing feature/step
   that reproduces the bug. Show the red before writing any fix.
2. **Plan Before Code**: Output a step-by-step plan of files to touch and wait for
   approval before generating the fix.
3. **Error Analysis**: If a test fails, analyze the exact error log. Do not guess.
   Explain the root cause before proposing a new solution.
4. **Micro-Tasks**: Break large fixes into single-function changes; keep each change
   covered by a test.
5. **Green**: Apply the fix, rerun the targeted test, then the full suite.

## Execution
- When invoked, ask the user for the specific issue.
- Enforce the "Test-First" rule strictly.
- If the user attempts to skip testing, remind them of this skill's protocol.
