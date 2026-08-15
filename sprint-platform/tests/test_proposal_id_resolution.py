"""
Unit test for proposal fixture-ID → real-UUID resolution (live Supabase).

Reproduces the original bug class: BDD step 'a draft proposal "p1" exists...'
seeds a proposal with id="p1"; seed_table() must convert it to a real UUID,
track the mapping, and later route/assertion steps resolve "p1" through
resolve_proposal_id() — otherwise a query against the uuid column raises:

  postgrest.exceptions.APIError: {'message': 'invalid input syntax for type uuid: "p1"'}

Runs against the live test project (like the behave suite) and cleans up the
rows it creates.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from services.supabase_client import get_supabase
from tests.live_db_adapter import LiveDBAdapter, set_static_job_ids


def _static_job_id(i: int) -> str:
    """Same deterministic uuid5 the BDD harness uses for static feed rows."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"sprint-platform-test:job:email-automation-{i}"))


def _make_adapter():
    """LiveDBAdapter on the real project, with static job ids registered."""
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret"})
    ctx = app.app_context()
    ctx.push()
    set_static_job_ids({f"email-automation-{i}": _static_job_id(i) for i in range(1, 6)})
    return app, ctx, LiveDBAdapter(get_supabase())


def test_proposal_id_tracked_and_resolved():
    """seed_table must track fixture→real proposal ID mapping for later resolution."""
    app, ctx, adapter = _make_adapter()
    try:
        real_sprint_id = adapter.resolve_sprint_id("s1")
        fixture_pid = "p1"
        adapter.seed_table("proposals", [{
            "id": fixture_pid,
            "sprint_id": real_sprint_id,
            "job_feed_id": "email-automation-1",
            "template_body": "test",
            "hooks": ["hook"],
            "status": "draft",
            "platform": None,
            "score": 85,
        }], on_conflict="id")

        assert hasattr(adapter, "resolve_proposal_id"), "LiveDBAdapter needs resolve_proposal_id()"
        real_id = adapter.resolve_proposal_id(fixture_pid)
        assert uuid.UUID(real_id), f"resolve_proposal_id returned non-UUID: {real_id}"

        # The real UUID should exist in the DB
        rows = adapter.sb.table("proposals").select("*").eq("id", real_id).execute().data
        assert rows, f"Proposal with resolved ID {real_id} not found in DB"
    finally:
        adapter.cleanup_scenario()
        ctx.pop()


def test_proposal_id_already_uuid_not_regenerated():
    """If the id is already a UUID, seed_table should not overwrite it."""
    app, ctx, adapter = _make_adapter()
    try:
        real_sprint_id = adapter.resolve_sprint_id("s1")
        real_uuid = str(uuid.uuid4())
        adapter.seed_table("proposals", [{
            "id": real_uuid,
            "sprint_id": real_sprint_id,
            "job_feed_id": "email-automation-1",
            "status": "draft",
            "score": 85,
        }], on_conflict="id")

        rows = adapter.sb.table("proposals").select("*").eq("id", real_uuid).execute().data
        assert rows, "Proposal with real UUID id was not found"
        assert rows[0]["id"] == real_uuid
    finally:
        adapter.cleanup_scenario()
        ctx.pop()


if __name__ == "__main__":
    test_proposal_id_tracked_and_resolved()
    print("PASS: test_proposal_id_tracked_and_resolved")
    test_proposal_id_already_uuid_not_regenerated()
    print("PASS: test_proposal_id_already_uuid_not_regenerated")
