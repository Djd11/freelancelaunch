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
import re

_STOPWORDS = {"with", "this", "that", "from", "your", "have", "will", "when",
              "then", "into", "they", "them", "their", "which", "where", "what",
              "should", "must", "need", "able", "using", "used", "step", "steps"}


def is_valid_url(url):
    """A submission URL counts as a real link only with an http(s) scheme."""
    return isinstance(url, str) and (url.startswith("http://") or url.startswith("https://"))


def record(sb, sprint_id, gate, status="pending", submitted_url=None, verification_type="auto", feedback=None, gate_b_evidence=None):
    """Upsert a verification review for (sprint, gate). One row per gate."""
    payload = {
        "sprint_id": sprint_id,
        "gate": gate,
        "status": status,
        "verification_type": verification_type,
        "submitted_url": submitted_url,
        "feedback": feedback,
    }
    if gate_b_evidence is not None:
        payload["gate_b_evidence"] = gate_b_evidence
    try:
        return sb.table("verification_reviews").upsert(
            payload, on_conflict="sprint_id,gate").execute()
    except Exception as exc:
        # Defensive: if migration 004 (gate_b_evidence column) has not been
        # applied to this environment yet, retry without the evidence column so
        # the review still records (the content check itself already ran above).
        # PostgREST surfaces the missing column as 42703 (raw) or PGRST204
        # (schema-cache miss) — match both.
        if gate_b_evidence is not None and ("42703" in str(exc) or "PGRST204" in str(exc)
                                           or "gate_b_evidence" in str(exc)):
            payload.pop("gate_b_evidence", None)
            return sb.table("verification_reviews").upsert(
                payload, on_conflict="sprint_id,gate").execute()
        raise


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
    submitted URL AND every project's rubric items are learner-ticked → pass.

    The self-checks are the consequence that makes practice real: a submission
    only counts done when the learner ticked all rubric items first (routes/
    sprints.py submit_copywork), so this gate can only pass work the learner
    actually verified themselves (content-quality P0-3).

    Called on every copy-work rubric submission. One review row per gate, so
    the submitted rubric URL is preserved through the pass write.
    """
    rows = sb.table("copywork_projects") \
        .select("done, submitted_url, rubric_checked").eq("sprint_id", sprint_id).execute().data

    def _self_checked(row):
        checked = row.get("rubric_checked") or []
        return len(checked) >= 3 and all(checked)

    if (rows and len(rows) >= 3
            and all(bool(r.get("done")) for r in rows)
            and all(is_valid_url(r.get("submitted_url")) for r in rows)
            and all(_self_checked(r) for r in rows)):
        return record(sb, sprint_id, "A", status="pass", verification_type="auto",
                      submitted_url=submitted_url)
    return None


def _acceptance_criteria(sb, sprint_id):
    """Mock-contract acceptance criteria = the sprint's capstone brief
    requirements (what the client actually asked for) — NOT the copy-work rubric
    (addresses critique I2: the deliverable is checked against its OWN brief, not
    against unrelated clone-work rubrics). Returns [] when no brief requirements
    exist (legacy pass path: URL + case study still gate)."""
    rows = sb.table("capstone_briefs").select("requirements") \
        .eq("sprint_id", sprint_id).limit(1).execute().data
    if not rows:
        return []
    reqs = rows[0].get("requirements") or ""
    return [r.strip() for r in str(reqs).split("\n") if r.strip()]


def _criterion_met(criterion, deliverable_text):
    """Robust artifact match (critique I2): a criterion counts as met when the
    deliverable contains at least 2 distinctive tokens (len>=4) from the
    criterion. Full-sentence substring matching was gameable (paste the rubric)
    and used the wrong artifact. Single-token hits are ignored to avoid
    accidental matches."""
    tokens = [t for t in re.findall(r"[a-z0-9]{4,}", criterion.lower())
              if t not in _STOPWORDS]
    if not tokens:
        return False
    low = deliverable_text.lower()
    hits = sum(1 for t in set(tokens) if t in low)
    need = 2 if len(tokens) >= 2 else len(tokens)
    return hits >= need


def _gate_b_artifact_check(sb, sprint_id, deliverable_text):
    """Content check for Gate B (content-quality P0-2): the submitted Mock
    Contract deliverable must satisfy the brief's acceptance criteria (not the
    copy-work rubrics). Returns None when there are no criteria to check (legacy
    path: a valid URL + a saved case study still gates), otherwise a dict with
    the pass verdict and which criteria were found in the deliverable."""
    criteria = _acceptance_criteria(sb, sprint_id)
    if not criteria:
        return None
    if not deliverable_text:
        return {"passed": False, "checked": criteria, "found": [],
                "reason": "no deliverable text supplied"}
    found = [c for c in criteria if _criterion_met(c, deliverable_text)]
    return {"passed": len(found) == len(criteria), "checked": criteria, "found": found}


def auto_check_gate_b(sb, sprint_id, deliverable_text=None):
    """Gate B auto-check: a valid deliverable URL on the review row AND a
    case study saved for the sprint AND (when rubric artifacts exist) the
    submitted deliverable actually contains those observable items → pass.

    Called after the Mock Contract deliverable is submitted. Keeps the
    submitted URL on the pass row and records gate_b_evidence (migration 004).
    """
    rows = sb.table("verification_reviews").select("submitted_url") \
        .eq("sprint_id", sprint_id).eq("gate", "B").limit(1).execute().data
    if not (rows and is_valid_url(rows[0].get("submitted_url"))):
        return None
    case_rows = sb.table("case_studies").select("id") \
        .eq("sprint_id", sprint_id).limit(1).execute().data
    if not case_rows:
        return None
    evidence = _gate_b_artifact_check(sb, sprint_id, deliverable_text)
    if evidence is None:
        # No rubric to check — legacy pass path (URL + case study present).
        return record(sb, sprint_id, "B", status="pass", verification_type="auto",
                      submitted_url=rows[0]["submitted_url"])
    if not evidence["passed"]:
        # Deliverable is missing the rubric artifacts → do NOT pass.
        return None
    return record(sb, sprint_id, "B", status="pass", verification_type="auto",
                  submitted_url=rows[0]["submitted_url"], gate_b_evidence=evidence)
