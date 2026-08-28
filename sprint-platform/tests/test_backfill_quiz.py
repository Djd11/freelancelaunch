"""Tests for quiz backfill of existing (legacy) lessons (content-quality P1-1/P1-2, F1-F5).

Uses a stateful in-memory fake of the Supabase client (mirrors the repo's
unit-test pattern in tests/test_atomic_rpc.py) so the 4 assertions run without
a live DB. `call_llm` is monkeypatched with a deterministic fake.
"""
import json
from unittest.mock import patch

from services.lesson_engine import backfill_quiz, quiz_from_lesson_prompt


GEN_QUIZ = [
    "What trigger starts the flow in this niche's tool?",
    "Which variable holds the dynamic content?",
    "How do you test the flow before going live?",
]
GEN_ANSWERS = [
    "The Checkout Started start event fires the flow in this niche's tool.",
    "The dynamic order-summary block bound to the cart object holds the content.",
    "Send a test event and confirm the email renders correctly in a live inbox.",
]


def _make_llm():
    """Fake call_llm: returns a generated quiz for the generation prompt and
    {"ok": true} for the verify/repair prompt (detected by the verify marker)."""
    calls = {"n": 0}

    def fake(prompt, **kwargs):
        calls["n"] += 1
        if "rigorous technical editor" in (prompt or ""):
            # _verify_lesson_quiz keeps the generated pair when ok:true
            return json.dumps({"ok": True})
        return json.dumps({"quiz": GEN_QUIZ, "quiz_answers": GEN_ANSWERS})

    fake.call_count = lambda: calls["n"]
    return fake


class _FakeSB:
    """Minimal stateful stand-in for the Supabase client used by backfill_quiz.

    Captures `update` payloads and applies them to the in-memory day rows so a
    second `backfill_quiz` call sees the post-backfill state (idempotency).
    `select(...).execute()` returns the current day rows; `update(...).eq(...).
    eq("day_no", n).execute()` commits the pending payload onto day n.
    """

    def __init__(self, days):
        self._days = {d["day_no"]: dict(d) for d in days}
        self._pending = None
        self._last_day = None
        self._mode = None
        self.update_calls = 0

    def table(self, _name):
        return self

    def select(self, *_a, **_k):
        self._mode = "read"
        return self

    def eq(self, col, val):
        if col == "day_no":
            self._last_day = val
        return self

    def order(self, *_a, **_k):
        return self

    def update(self, payload):
        self._pending = payload
        self._mode = "write"
        return self

    def execute(self):
        if self._mode == "read":
            class _R:
                pass
            r = _R()
            r.data = [dict(d) for d in self._days.values()]
            self._mode = None
            return r
        # write mode: flush the pending update onto the targeted day
        if self._pending is not None and self._last_day is not None:
            day = self._days.get(self._last_day, {})
            if "action_payload" in self._pending:
                day["action_payload"] = self._pending["action_payload"]
            self.update_calls += 1
            self._pending = None
        self._mode = None
        class _R:
            pass
        r = _R()
        r.data = []
        return r


def _lesson():
    return {
        "title": "Rebuild the Checkout Welcome Flow",
        "script": "Open the tool, set the Checkout Started trigger, add the message step, test it.",
        "key_points": ["Use the exact trigger", "Follow the build sequence"],
        "pitfalls": ["Skipping the test step", "Wrong trigger"],
    }


# ── Assertion 1: quiz-less lesson gains a valid quiz ──────────────────
def test_quiz_less_lesson_gains_quiz():
    sb = _FakeSB([{"day_no": 2, "action_payload": {"lesson": _lesson()}}])
    llm = _make_llm()
    with patch("services.lesson_engine.call_llm", llm):
        updated = backfill_quiz(sb, "s1")
    assert updated == 1, f"expected 1 updated day, got {updated}"
    lesson = sb._days[2]["action_payload"]["lesson"]
    assert "quiz" in lesson and "quiz_answers" in lesson
    assert 3 <= len(lesson["quiz"]) <= 4, f"quiz len {len(lesson['quiz'])} not in 3-4"
    assert len(lesson["quiz"]) == len(lesson["quiz_answers"]), "quiz/answers length mismatch"
    assert lesson["quiz_answers"] == GEN_ANSWERS


# ── Assertion 2: existing content is byte-identical (surgical merge) ───
def test_existing_content_preserved():
    original = _lesson()
    sb = _FakeSB([{"day_no": 2, "action_payload": {"lesson": dict(original)}}])
    llm = _make_llm()
    with patch("services.lesson_engine.call_llm", llm):
        backfill_quiz(sb, "s1")
    lesson = sb._days[2]["action_payload"]["lesson"]
    assert lesson["title"] == original["title"]
    assert lesson["script"] == original["script"]
    assert lesson["key_points"] == original["key_points"]
    assert lesson["pitfalls"] == original["pitfalls"]


# ── Assertion 3: idempotent re-run changes nothing ────────────────────
def test_idempotent_rerun_changes_nothing():
    sb = _FakeSB([{"day_no": 2, "action_payload": {"lesson": _lesson()}}])
    llm = _make_llm()
    with patch("services.lesson_engine.call_llm", llm):
        n1 = backfill_quiz(sb, "s1")
    assert n1 == 1
    first = json.loads(json.dumps(sb._days[2]["action_payload"]["lesson"]))
    with patch("services.lesson_engine.call_llm", llm):
        n2 = backfill_quiz(sb, "s1")
    assert n2 == 0, f"idempotent re-run should update 0 days, got {n2}"
    second = sb._days[2]["action_payload"]["lesson"]
    assert second["quiz"] == first["quiz"]
    assert second["quiz_answers"] == first["quiz_answers"]
    # No extra LLM generation happened on the second pass (skipped before call_llm)
    assert llm.call_count() == 2, f"expected exactly 2 LLM calls (gen+verify), got {llm.call_count()}"


# ── Assertion 4: already-quizzed lesson is untouched ──────────────────
def test_already_quizzed_untouched():
    lesson = dict(_lesson())
    lesson["quiz"] = ["Existing question one?"]
    lesson["quiz_answers"] = ["Existing specific answer one."]
    sb = _FakeSB([{"day_no": 2, "action_payload": {"lesson": lesson}}])
    llm = _make_llm()
    with patch("services.lesson_engine.call_llm", llm):
        updated = backfill_quiz(sb, "s1")
    assert updated == 0, f"already-quizzed day should not be updated, got {updated}"
    assert llm.call_count() == 0, "no LLM call expected for an already-valid lesson"
    assert sb._days[2]["action_payload"]["lesson"]["quiz"] == ["Existing question one?"]
    assert sb._days[2]["action_payload"]["lesson"]["quiz_answers"] == ["Existing specific answer one."]


# ── F3 guard: generation prompt must NOT be the verify prompt ─────────
def test_quiz_from_lesson_prompt_is_generation_not_verify():
    prompt = quiz_from_lesson_prompt(_lesson())
    # The verify prompt is identified by this marker in _quiz_verify_prompt;
    # reusing it would make backfill a no-op (early-return at line 318).
    assert "rigorous technical editor" not in prompt
    # It must carry the lesson content so the model can ground the questions.
    assert "LESSON:" in prompt
    assert "Checkout Started" in prompt
