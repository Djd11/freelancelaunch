"""
verification_service — the two gates (engineering-spec §4.2, arch §5.4).
Gate A: Phase A→B (3 copy-work rubrics + gap-fill auto-checked).
Gate B: Phase B→C (Mock Contract deliverable auto/peer review).
A lock never silently breaks: if a gate is required but absent, the UI shows
the lock + the missing item.

auto_check_gate_a / auto_check_gate_b are the deterministic auto-check paths
(arch §7: "Verification (auto): contract submit → inline auto-test"). Peer
review (design/copy) is a manual pass written through record() by an admin.
"""


def is_valid_url(url):
    """A submission URL counts as a real link only with an http(s) scheme."""
    return isinstance(url, str) and (url.startswith("http://") or url.startswith("https://"))


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


def auto_check_gate_a(sb, sprint_id, submitted_url=None):
    """Gate A auto-check: all 3 copy-work projects done AND each has a valid
    submitted URL → pass.

    Called on every copy-work rubric submission. One review row per gate, so
    the submitted rubric URL is preserved through the pass write.
    """
    rows = sb.table("copywork_projects").select("done, submitted_url").eq("sprint_id", sprint_id).execute().data
    if (rows and len(rows) >= 3
            and all(bool(r.get("done")) for r in rows)
            and all(is_valid_url(r.get("submitted_url")) for r in rows)):
        return record(sb, sprint_id, "A", status="pass", verification_type="auto",
                      submitted_url=submitted_url)
    return None


def auto_check_gate_b(sb, sprint_id):
    """Gate B auto-check: a valid deliverable URL on the review row AND a
    case study saved for the sprint → pass.

    Called after the Mock Contract deliverable is submitted. Keeps the
    submitted URL on the pass row.
    """
    rows = sb.table("verification_reviews").select("submitted_url") \
        .eq("sprint_id", sprint_id).eq("gate", "B").limit(1).execute().data
    if not (rows and is_valid_url(rows[0].get("submitted_url"))):
        return None
    case_rows = sb.table("case_studies").select("id") \
        .eq("sprint_id", sprint_id).limit(1).execute().data
    if not case_rows:
        return None
    return record(sb, sprint_id, "B", status="pass", verification_type="auto",
                  submitted_url=rows[0]["submitted_url"])
