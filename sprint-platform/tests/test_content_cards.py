"""Dashboard Sprint Content cards — pure builder (unit, no DB)."""
from services.lesson_engine import content_day_cards


def test_ok_day_when_lesson_present():
    rows = [{"day_no": 1, "action_type": "setup", "is_done": True,
             "action_payload": {"lesson": {"title": "Day 1 Orientation"}}}]
    assert content_day_cards(rows) == [
        {"day_no": 1, "action_type": "setup", "is_done": True,
         "lesson_title": "Day 1 Orientation", "status": "ok"}]


def test_error_day_when_generation_error_stamped():
    rows = [{"day_no": 3, "action_type": "copywork", "is_done": False,
             "action_payload": {"generation_error": "Generation failed: boom"}}]
    card = content_day_cards(rows)[0]
    assert card["status"] == "error"
    assert card["lesson_title"] == ""


def test_pending_day_when_payload_empty():
    rows = [{"day_no": 7, "action_type": "proposal", "is_done": False,
             "action_payload": {}}]
    assert content_day_cards(rows)[0]["status"] == "pending"


def test_missing_payload_key_is_pending():
    rows = [{"day_no": 7, "action_type": "contract", "is_done": False}]
    assert content_day_cards(rows)[0]["status"] == "pending"
