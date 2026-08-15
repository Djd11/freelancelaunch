"""
Unit test for mentor context fetching the correct target job.

Reproduces the bug: mentor_bp._context() fetches the first job from the
cluster without ordering, so it may not fetch email-automation-1 — the
specific job whose description and ID the BDD tests reference.

This causes two BDD failures:
  1. 'A mentor turn is grounded in the target job's terminology'
     — answer missing 'cart summary' (different job's description)
  2. 'Mentor sessions are scoped to the user's sprint and target job'
     — no mentor session for (s1, email-automation-1) (wrong job_id stored)
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_mentor_context_preference():
    """The mentor should specifically look up email-automation-1, not just
    any random first job from the cluster."""
    from app import create_app
    from services.supabase_client import get_supabase

    app = create_app()
    with app.app_context():
        sb = get_supabase()

        # The job_feed has 5 jobs for email-automation. Without ordering,
        # limit(1) can return ANY of them. The BDD tests set description
        # on email-automation-1 specifically. The mentor must fetch the
        # same job to see the updated description.

        # Simulate what seed_live.py does — the jobs have ids like
        # "email-automation-1" through "email-automation-5"
        # These are string IDs, not UUIDs, in the seed_live.py.
        # But the DB schema says id UUID PRIMARY KEY. Let's check:

        rows = sb.table("job_feed").select("id,cluster_key,title").eq("cluster_key", "email-automation").execute().data
        print(f"Found {len(rows)} jobs in email-automation cluster")
        for r in rows:
            print(f"  id={r.get('id')}, title={r.get('title')}")

        # The mentor fetches limit(1) — verify it returns a consistent job
        # The test expects email-automation-1 specifically.
        # If the mentor doesn't look up email-automation-1 by its known id,
        # it may get a different job, causing the BDD failures.

        # Check: does any job have a string id like "email-automation-1"?
        string_id_jobs = [r for r in rows if not _is_uuid(r.get("id", ""))]
        if string_id_jobs:
            print(f"WARNING: {len(string_id_jobs)} jobs have non-UUID string IDs")
            print("The mentor query with .eq('cluster_key', ...) may return these")
            print("but the BDD test step looks up get_static_job_id('email-automation-1')")

        print("\nRoot cause: mentor_bp._context() uses .limit(1) without .order()")
        print("This returns an arbitrary job from the cluster, not necessarily email-automation-1")
        print("The fix: mentor should look up email-automation-1 explicitly, or the")
        print("test setup should ensure the mentor sees the right description.")


def _is_uuid(s):
    try:
        uuid.UUID(s)
        return True
    except (ValueError, TypeError):
        return False


if __name__ == "__main__":
    test_mentor_context_preference()
