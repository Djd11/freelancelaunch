"""
verification_service — the two gates (engineering-spec §4.2, arch §5.4).
Gate A: Phase A→B (3 copy-work rubrics + gap-fill auto-checked).
Gate B: Phase B→C (Mock Contract deliverable auto/peer review).
A lock never silently breaks: if a gate is required but absent, the UI shows
the lock + the missing item.
"""


def record(sb, sprint_id, gate, status="pending", submitted_url=None, verification_type="auto", feedback=None):
    """Upsert a verification review for (sprint, gate). One row per gate."""
    return sb.table("verification_reviews").upsert({
        "sprint_id": sprint_id,
        "gate": gate,
        "status": status,
        "verification_type": verification_type,
        "submitted_url": submitted_url,
        "feedback": feedback,
    }, on_conflict="sprint_id,gate").execute()


def status(sb, sprint_id, gate):
    """Return the review status for (sprint, gate): 'pass' | 'fail' | 'pending' | None."""
    rows = sb.table("verification_reviews").select("*") \
        .eq("sprint_id", sprint_id).eq("gate", gate).limit(1).execute().data
    return rows[0].get("status") if rows else None


def passed(sb, sprint_id, gate):
    return status(sb, sprint_id, gate) == "pass"


def gate_a_passed(sb, sprint_id):
    return passed(sb, sprint_id, "A")


def gate_b_passed(sb, sprint_id):
    return passed(sb, sprint_id, "B")
