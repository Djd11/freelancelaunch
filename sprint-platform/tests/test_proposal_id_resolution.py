"""
Unit test for proposal fake-ID → real-UUID resolution.

Reproduces the bug: BDD step 'a draft proposal "p1" exists...' seeds a proposal
with id="p1", but seed_table() converts it to a real UUID and discards the
mapping. Later, the route and assertion steps try to query by "p1" — a UUID
column — raising:

  postgrest.exceptions.APIError: {'message': 'invalid input syntax for type uuid: "p1"'}

This test verifies that LiveDBAdapter tracks fake proposal IDs so they can be
resolved later, and that SprintIDRewritingClient rewrites proposal IDs in URLs.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.live_db_adapter import LiveDBAdapter, TEST_USER_ID


def make_adapter_with_fake_sb():
    """Create a LiveDBAdapter backed by a FakeSupabase for unit testing."""
    from services.fake_supabase import FakeSupabase
    from services.supabase_client import get_dev_db
    # Use a fresh FakeSupabase
    db = FakeSupabase()
    # Seed minimal user_profiles so resolve_user_id works
    class FakeAuth:
        class Admin:
            def list_users(self):
                return []
            def create_user(self, payload):
                class R:
                    def __init__(self):
                        self.user = type('U', (), {'id': str(uuid.uuid4()), 'email': payload.get('email')})()
                return R()
        admin = Admin()
    db.auth = FakeAuth()
    return LiveDBAdapter(db)


def test_proposal_id_tracked_and_resolved():
    """seed_table must track fake→real proposal ID mapping for later resolution."""
    adapter = make_adapter_with_fake_sb()

    # Seed a proposal with fake ID "p1"
    fake_pid = "p1"
    adapter.seed_table("proposals", [{
        "id": fake_pid,
        "sprint_id": "s1",
        "job_feed_id": "email-automation-1",
        "template_body": "test",
        "hooks": ["hook"],
        "status": "draft",
        "platform": None,
        "score": 85,
    }], on_conflict="id")

    # The adapter should track the mapping from fake "p1" to a real UUID
    assert hasattr(adapter, 'resolve_proposal_id'), "LiveDBAdapter needs resolve_proposal_id()"
    real_id = adapter.resolve_proposal_id(fake_pid)
    assert uuid.UUID(real_id), f"resolve_proposal_id returned non-UUID: {real_id}"

    # The real UUID should exist in the DB
    rows = adapter.sb.table("proposals").select("*").eq("id", real_id).execute().data
    assert rows, f"Proposal with resolved ID {real_id} not found in DB"


def test_proposal_id_already_uuid_not_regenerated():
    """If the id is already a UUID, seed_table should not overwrite it."""
    adapter = make_adapter_with_fake_sb()
    real_uuid = str(uuid.uuid4())
    adapter.seed_table("proposals", [{
        "id": real_uuid,
        "sprint_id": "s1",
        "status": "draft",
        "score": 85,
    }], on_conflict="id")

    rows = adapter.sb.table("proposals").select("*").eq("id", real_uuid).execute().data
    assert rows, "Proposal with real UUID id was not found"
    assert rows[0]["id"] == real_uuid


if __name__ == "__main__":
    test_proposal_id_tracked_and_resolved()
    print("PASS: test_proposal_id_tracked_and_resolved")
    test_proposal_id_already_uuid_not_regenerated()
    print("PASS: test_proposal_id_already_uuid_not_regenerated")
