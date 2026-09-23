"""Cluster content library — cohort amortization (arch §2 P3).

The 14-day course content is provisioned ONCE per cluster under admin
control; every learner enrolling consumes it with ZERO per-user LLM calls.
These unit tests run against an in-memory PostgREST fake so they exercise
the pure service logic (generate → apply → admin edit → seed) without the
live Supabase project.
"""
import json
import sys
import types

import pytest

# ── In-memory PostgREST-ish fake ──────────────────────────────────────


class _Table:
    def __init__(self, db, name):
        self.db, self.name = db, name
        self._op = None
        self._eq = []
        self._order = None

    def _rows(self):
        return self.db.setdefault(self.name, [])

    def select(self, *cols):
        return self

    def insert(self, row):
        self._op = ("insert", row)
        return self

    def update(self, row):
        self._op = ("update", row)
        return self

    def upsert(self, row, on_conflict=None):
        self._op = ("upsert", row, on_conflict)
        return self

    def delete(self):
        self._op = ("delete", None)
        return self

    def eq(self, col, val):
        self._eq.append((col, val))
        return self

    def order(self, col):
        self._order = col
        return self

    def limit(self, n):
        return self

    def execute(self):
        op, eqs, rows = self._op, list(self._eq), self._rows()
        self._eq = []

        def match(r):
            return all(r.get(c) == v for c, v in eqs)

        R = lambda d: types.SimpleNamespace(data=d)  # noqa: E731
        if op and op[0] == "insert":
            rows.append(dict(op[1]))
            self._op = None
            return R([dict(rows[-1])])
        if op and op[0] == "update":
            for r in rows:
                if match(r):
                    r.update(op[1])
            self._op = None
            return R([])
        if op and op[0] == "upsert":
            row, oc = op[1], op[2]
            cols = [c.strip() for c in (oc or "").split(",") if c.strip()]
            found = [r for r in rows if all(r.get(c) == row.get(c) for c in cols)]
            if found:
                found[0].update(row)
            else:
                rows.append(dict(row))
            self._op = None
            return R([])
        if op and op[0] == "delete":
            self.db[self.name] = [r for r in rows if not match(r)]
            self._op = None
            return R([])
        data = [dict(r) for r in rows if match(r)]
        data.sort(key=lambda r: r.get(self._order, 0) or 0)
        return R(data)


class FakeSB:
    def __init__(self):
        self.db = {}

    def table(self, name):
        return _Table(self.db, name)


# ── Deterministic LLM stub (same shape lesson_engine's generators emit) ──


FAKE_LESSON = {
    "title": "Day lesson for Klaviyo flow setup for store",
    "objective": "Complete the day's task.",
    "script": "In this lesson you will learn how to handle the flow. " * 4,
    "key_points": ["Use the exact trigger from the job posting"],
    "pitfalls": ["Skipping the test step"],
    "quiz": ["What trigger starts the flow?"],
    "quiz_answers": ["The start event named in the posting."],
    "hook": "Land your first Klaviyo automation gig faster.",
    "day_overview": ["Configure the right trigger"],
    "usefulness_context": "Clients repeatedly post Klaviyo flow jobs.",
    "pre_quiz": [{"q": "What event starts the flow?",
                  "options": ["Checkout Started", "Order Refunded"], "answer": 0}],
}


@pytest.fixture()
def sb():
    db = FakeSB()
    db.db["job_clusters"] = [{"cluster_key": "email-automation",
                              "keywords": ["klaviyo", "email"]}]
    db.db["job_feed"] = [{
        "id": "j1", "cluster_key": "email-automation",
        "title": "Klaviyo flow setup for store", "description": "Build flows",
        "skills": ["klaviyo"], "status": "active", "unlock_day": 1,
        "source_platform": "manual",
    }]
    return db


@pytest.fixture()
def llm_stub(monkeypatch):
    import services.lesson_engine as le

    calls = {"n": 0}

    def fake_llm(prompt, **kwargs):
        calls["n"] += 1
        import re
        m = re.search(r"project (\d) of 3", prompt or "")
        if m:
            i = m.group(1)
            return json.dumps({"title": f"P{i} flow", "clone_steps": ["s1", "s2", "s3"],
                               "rubric": ["r1", "r2", "r3"], "gap_fill_topic": None,
                               "reference_spec": "Screen 1"})
        return json.dumps(FAKE_LESSON)

    monkeypatch.setattr(le, "call_llm", fake_llm)
    return calls


def _seed_sprint(sb, sprint_id="SPR-1", with_days=True):
    sb.db["sprints"] = [{"id": sprint_id, "cluster_key": "email-automation",
                         "user_id": "u1", "status": "active", "started_at": "now"}]
    if with_days:
        sb.db["sprint_days"] = [
            {"id": f"d{i}", "sprint_id": sprint_id, "day_no": i, "phase": "A",
             "action_type": "copywork", "title": f"Day {i}",
             "action_payload": {}, "is_done": False}
            for i in range(1, 15)
        ]
        sb.db["copywork_projects"] = [
            {"id": f"p{i}", "sprint_id": sprint_id, "project_index": i,
             "title": "placeholder", "source_url": "", "clone_steps": [],
             "rubric": [], "done": False}
            for i in range(1, 4)
        ]


# ── Tests ─────────────────────────────────────────────────────────────


def test_generate_for_cluster_provisions_full_library(sb, llm_stub):
    from services.content_library import generate_for_cluster, library_status
    result = generate_for_cluster(sb, "email-automation")
    assert result == {"days": 14, "projects": 3}
    status = library_status(sb, "email-automation")
    assert status["ready"] is True
    # 14 lessons + 3 anatomies; the quiz-verify pass adds one call per lesson
    # (the stub's answers pass verification → 31 total).
    assert llm_stub["n"] == 31, llm_stub


def test_apply_library_to_sprint_is_zero_llm_and_idempotent(sb, llm_stub):
    from services.content_library import (
        apply_library_to_sprint, generate_for_cluster,
    )
    generate_for_cluster(sb, "email-automation")
    _seed_sprint(sb)

    before = llm_stub["n"]
    n = apply_library_to_sprint(sb, "SPR-1", "email-automation")
    assert n == 14
    assert llm_stub["n"] == before, "applying the library must make NO LLM calls"

    days = {r["day_no"]: r for r in sb.db["sprint_days"]}
    assert days[3]["action_payload"]["lesson"]["script"].startswith("In this lesson")
    assert sb.db["copywork_projects"][0]["clone_steps"] == ["s1", "s2", "s3"]
    # idempotent re-apply never clobbers
    assert apply_library_to_sprint(sb, "SPR-1", "email-automation") == 14


def test_apply_library_partial_fill_only_empty_days(sb, llm_stub):
    """Days that already carry a lesson (learner progress) are never clobbered;
    only empty days get library content."""
    from services.content_library import (
        apply_library_to_sprint, generate_for_cluster,
    )
    generate_for_cluster(sb, "email-automation")
    _seed_sprint(sb)
    own = {"title": "Learner's own day", "script": "custom"}
    sb.db["sprint_days"][6]["action_payload"] = {"lesson": own}

    n = apply_library_to_sprint(sb, "SPR-1", "email-automation")
    assert n == 14
    assert sb.db["sprint_days"][6]["action_payload"]["lesson"] == own


def test_admin_edit_overrides_day_for_new_learners(sb, llm_stub):
    from services.content_library import (
        apply_library_to_sprint, generate_for_cluster, library_days, update_day,
    )
    generate_for_cluster(sb, "email-automation")
    update_day(sb, "email-automation", 7, {"title": "Pricing your first contract"})
    assert library_days(sb, "email-automation")[7]["title"] == "Pricing your first contract"

    _seed_sprint(sb, "SPR-2")
    apply_library_to_sprint(sb, "SPR-2", "email-automation")
    days = {r["day_no"]: r for r in sb.db["sprint_days"]}
    assert days[7]["action_payload"]["lesson"]["title"] == "Pricing your first contract"


def test_seed_from_sprint_bootstrap(sb, llm_stub):
    from services.content_library import seed_from_sprint
    _seed_sprint(sb)
    for d in sb.db["sprint_days"]:
        d["action_payload"] = {"lesson": dict(FAKE_LESSON)}
    # Anatomy copy needs non-empty clone_steps AND rubric on the project rows.
    for p in sb.db["copywork_projects"]:
        p["clone_steps"] = ["s1", "s2", "s3"]
        p["rubric"] = ["r1", "r2", "r3"]
    copied = seed_from_sprint(sb, "web-scraping", "SPR-1", overwrite=True)
    assert copied == {"days": 14, "projects": 3}


def test_regenerate_skips_existing_rows(sb, llm_stub):
    from services.content_library import generate_for_cluster
    generate_for_cluster(sb, "email-automation")
    assert generate_for_cluster(sb, "email-automation") == {"days": 0, "projects": 0}
    # and no NEW LLM calls happened on the second run
    assert llm_stub["n"] == 31


def test_try_fill_from_library_repairs_existing_empty_sprint(sb, llm_stub):
    """THE REPORTED BUG: a sprint created before the library existed (its days
    empty, per-user LLM failing) must be repaired from the library with zero
    LLM calls when the learner hits the day view."""
    from services.content_library import (
        generate_for_cluster, try_fill_from_library,
    )
    # Sprint exists FIRST, library provisioned AFTER (the deployment-gap order).
    _seed_sprint(sb)
    generate_for_cluster(sb, "email-automation")

    before = llm_stub["n"]
    filled = try_fill_from_library(sb, "SPR-1")
    assert filled is True
    assert llm_stub["n"] == before, "repair must make zero LLM calls"

    import services.lesson_engine as le
    generated, total = le.generation_progress(sb, "SPR-1")
    assert generated == total == 14


def test_try_fill_from_library_noop_when_no_library(sb, llm_stub):
    from services.content_library import try_fill_from_library
    _seed_sprint(sb)
    assert try_fill_from_library(sb, "SPR-1") is False


def test_try_fill_from_library_noop_when_already_full(sb, llm_stub):
    from services.content_library import (
        apply_library_to_sprint, generate_for_cluster, try_fill_from_library,
    )
    generate_for_cluster(sb, "email-automation")
    _seed_sprint(sb)
    apply_library_to_sprint(sb, "SPR-1", "email-automation")
    # Second call: nothing empty left → False (no work), zero LLM.
    before = llm_stub["n"]
    assert try_fill_from_library(sb, "SPR-1") is False
    assert llm_stub["n"] == before
