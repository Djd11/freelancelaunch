"""
Sprint Planner — builds the 14-day sprint plan (Phase A/B/C) for a cluster.

Phase A (Days 1-5):  Skill Acquisition via Copy-Work.
   Day 1 tool setup · Days 2-4 three replication projects · Day 5 gap-fill.
Phase B (Days 6-10): Mock Contract (brief → execute → case study).
Phase C (Days 11-14): Supply Chain (proposal → first-bid → iteration).

Each sprint_day rows carries an action_type + action_payload so the day
renderer knows exactly which phase-specific UI to show. Reuses the v1
curriculum_generator for Learn bodies when available.
"""
import logging
from services.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# (day_no, phase, action_type, title)
PLAN = [
    (1,  "A", "setup",    "Tool Setup & Environment"),
    (2,  "A", "copywork", "Copy-Work · Project 1"),
    (3,  "A", "copywork", "Copy-Work · Project 2"),
    (4,  "A", "copywork", "Copy-Work · Project 3"),
    (5,  "A", "gapfill",  "Gap-Fill Micro-Lesson"),
    (6,  "B", "contract", "Mock Contract · Read the Brief"),
    (7,  "B", "contract", "Mock Contract · Execute Part 1"),
    (8,  "B", "contract", "Mock Contract · Execute Part 2"),
    (9,  "B", "contract", "Case Study · Problem & Solution"),
    (10, "B", "contract", "Case Study · Result & Polish"),
    (11, "C", "proposal", "Proposal Engineering"),
    (12, "C", "proposal", "First-Bid Challenge · Proposals 1-2"),
    (13, "C", "proposal", "First-Bid Challenge · Proposals 3-5"),
    (14, "C", "proposal", "Iteration Loop & Remediation"),
]

PHASE_DESCRIPTIONS = {
    "A": "Skill Acquisition — rebuild real projects to build muscle memory.",
    "B": "Mock Contract — fulfill a real anonymized brief like it's paid.",
    "C": "Supply Chain — engineered proposals and the First-Bid challenge.",
}


def phase_for_day(day_no):
    for d, phase, _a, _t in PLAN:
        if d == day_no:
            return phase
    return "C"


def build_plan(sb=None, sprint_id=None, cluster_key=None):
    """Create the 14 sprint_days for a sprint. Idempotent per sprint."""
    sb = sb or get_supabase()
    existing = sb.table("sprint_days").select("id").eq("sprint_id", sprint_id).limit(1).execute()
    if existing.data:
        return existing.data

    for day_no, phase, action_type, title in PLAN:
        payload = {}
        if action_type == "copywork":
            # project 1..3 on days 2..4
            payload = {"project_index": day_no - 1}
        elif action_type == "gapfill":
            payload = {"detect": True}
        elif action_type == "contract":
            payload = {"step": {"6": "brief", "7": "execute1", "8": "execute2", "9": "case-problem", "10": "case-result"}.get(str(day_no), "execute")}
        elif action_type == "proposal":
            payload = {"step": "engineer" if day_no == 11 else ("first-bid" if day_no in (12, 13) else "iterate")}
        try:
            sb.table("sprint_days").insert({
                "sprint_id": sprint_id,
                "phase": phase,
                "day_no": day_no,
                "title": title,
                "description": PHASE_DESCRIPTIONS.get(phase, ""),
                "action_type": action_type,
                "action_payload": payload,
                "is_done": False,
            }).execute()
        except Exception as e:
            logger.warning(f"build_plan insert day {day_no} failed: {e}")

    logger.info(f"Built 14-day sprint plan for sprint {sprint_id}")
    return sb.table("sprint_days").select("*").eq("sprint_id", sprint_id).order("day_no").execute().data
