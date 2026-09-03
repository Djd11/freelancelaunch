"""
sprint_planner — 14-day plan generation (architecture.md §4.3, eng-spec §5).

v1 generates the deterministic 14-day skeleton synchronously at sprint
creation — DB-backed sprint_days rows with a static phase map, no LLM
required, so every request stays fast and offline-safe (No-500 philosophy).

The async upgrade path from eng-spec §5 (background thread + DB-backed
progress log + frontend polling) is supported by the schema — a generation
status column and a worker can be layered on without touching the day rows
this service produces.
"""

# Day → phase. Phase A = days 1-5 (Copy-Work), B = 6-10 (Mock Contract),
# C = 11-14 (Send Proposals). Mirrors eng-spec §3 J3 and the schema CHECK.
PHASE_MAP = {d: "A" for d in range(1, 6)} | {d: "B" for d in range(6, 11)} | {d: "C" for d in range(11, 15)}


def action_for(day):
    """The phase-specific action a day renders (eng-spec J4: 'every Phase A/C/B
    day renders the correct phase-specific action from sprint_days.action_type')."""
    if day == 1:
        return "setup"          # Watch + account setup, then the first Copy-Work project
    if day < 6:
        return "copywork"
    if day <= 8:
        return "contract"       # execute the Mock Contract flow
    if day <= 10:
        return "case-study"     # write Problem / Solution / Result
    return "proposal"           # First-Bid challenge


def create_plan(sb, sprint_id):
    """Insert the 14 sprint_days rows for a new sprint. Idempotent per sprint
    (UNIQUE(sprint_id, day_no) makes re-runs a no-op via upsert)."""
    for d in range(1, 15):
        sb.table("sprint_days").upsert({
            "sprint_id": sprint_id,
            "phase": PHASE_MAP[d],
            "day_no": d,
            "title": f"Day {d}",
            "description": "",
            "action_type": action_for(d),
            "action_payload": {},
            "is_done": False,
        }, on_conflict="sprint_id,day_no").execute()
    return True
