"""Backfill quiz/quiz_answers for an existing sprint's legacy lessons.

Pre-feature lessons never received a quiz, and the content worker skips
already-generated days, so this one-off runner generates a quiz for each day
that needs one via services.lesson_engine.backfill_quiz.

Usage:
    python scripts/backfill_quiz.py <sprint_id>

Requires Supabase credentials (services.supabase_client) and a working LLM
provider (services.llm.call_llm). Run once per sprint; the function is
idempotent and safe to re-invoke.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/backfill_quiz.py <sprint_id>")
        sys.exit(2)
    sprint_id = sys.argv[1]
    from app import create_app
    from services.supabase_client import get_supabase
    from services.lesson_engine import backfill_quiz

    app = create_app()
    with app.app_context():
        sb = get_supabase()
        updated = backfill_quiz(sb, sprint_id)
    print(f"backfill complete: {updated} day(s) updated for sprint {sprint_id}")


if __name__ == "__main__":
    main()
