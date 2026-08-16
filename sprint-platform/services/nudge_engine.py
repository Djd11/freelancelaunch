"""
nudge_engine — Momentum nudges (engineering-spec §4.4, mockup sprint screen).
Rule-based encouragement scoped to where the user is in the sprint.
"""
import random

_PHASE_A = ("You're past the hardest part of a new skill. 3 days of Copy-Work "
            "builds more muscle memory than 30 days of videos — keep going.")
_PHASE_B = ("This mock contract is the closest thing to a real paycheck you'll "
            "feel this week. Ship the case study and you've got your first proof.")
_PHASE_C = ("5 proposals, one diagnosis loop. Send the next one — momentum "
            "compounds at the finish line.")


def recompute_confidence(current):
    """Confidence recompute on a progress mark (eng-spec §4.4: confidence is
    recomputed by the nudge engine on every progress mark)."""
    return min(100, (current or 50) + 3)


def nudge(sprint, momentum):
    phase = sprint.get("phase", "A")
    if phase == "A":
        return _PHASE_A
    if phase == "B":
        return _PHASE_B
    return _PHASE_C
