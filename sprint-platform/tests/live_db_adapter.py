"""
Live-DB BDD Adapter — maps readable test IDs to real Supabase UUIDs.

The BDD features/steps use readable fixture identifiers ("test-user-123",
"s1", "email-automation-1"). This adapter rewires them onto the REAL
Supabase project:
- Test user IDs → real auth.users UUIDs (created once, cached)
- Test sprint IDs → real sprints.id UUIDs (created per scenario, tracked)
- FK order cleanup: children first → parents last
"""

import uuid
from contextlib import contextmanager
import uuid as _uuid
from typing import Any, Dict, List, Optional

from services.supabase_client import get_supabase


# Well-known fixture IDs used in BDD steps
TEST_USER_ID = "test-user-123"
OTHER_USER_ID = "other-user-999"
ADMIN_USER_ID = "admin-user"

# Module-level storage for static data that persists across scenarios
_static_data = {
    "job_ids": {},       # fixture job ID -> real UUID
    "cohort_id": None,   # real UUID
}


def get_static_job_id(fixture_id: str) -> str:
    """Get real UUID for a fixture job ID, or return the fixture ID if not mapped."""
    return _static_data["job_ids"].get(fixture_id, fixture_id)


def get_static_cohort_id() -> Optional[str]:
    """Get the real cohort UUID."""
    return _static_data["cohort_id"]


def set_static_job_ids(job_ids: Dict[str, str]):
    _static_data["job_ids"] = job_ids


def set_static_cohort_id(cohort_id: str):
    _static_data["cohort_id"] = cohort_id


class LiveDBAdapter:
    """Maps readable fixture IDs to real Supabase UUIDs and manages per-scenario data."""

    def __init__(self, sb):
        self.sb = sb
        self._fixture_to_real_user: Dict[str, str] = {}
        self._fixture_to_real_sprint: Dict[str, str] = {}
        self._fixture_to_real_proposal: Dict[str, str] = {}
        self._created_sprints: List[str] = []
        self._created_rows: Dict[str, List[str]] = {}  # table -> list of real IDs

    # ──────────────────────────────────────────────────────────────
    # USER ID MAPPING
    # ──────────────────────────────────────────────────────────────

    def resolve_user_id(self, fixture_id: str) -> str:
        """Map a fixture user ID to a real auth user UUID."""
        if fixture_id in self._fixture_to_real_user:
            return self._fixture_to_real_user[fixture_id]

        # Special well-known fixture IDs
        if fixture_id == "test-user-123":
            real_id = self._ensure_demo_user()
        elif fixture_id == "other-user-999":
            real_id = self._ensure_other_user()
        elif fixture_id == "admin-user":
            real_id = self._ensure_admin_user()
        elif fixture_id == "demo-user":
            real_id = self._ensure_demo_user()
        else:
            # Create a new test user for any other fixture ID
            real_id = self._create_test_user(fixture_id)

        self._fixture_to_real_user[fixture_id] = real_id
        return real_id

    def _ensure_demo_user(self) -> str:
        """Get or create the demo user (Maya Chen)."""
        # Look for existing demo user by email
        try:
            users = self.sb.auth.admin.list_users()
            for u in users:
                if u.email == "demo@sprint-platform.local":
                    return u.id
        except Exception:
            pass

        # Create if not found
        resp = self.sb.auth.admin.create_user({
            "email": "demo@sprint-platform.local",
            "password": "demo-password-123",
            "email_confirm": True,
            "user_metadata": {"display_name": "Maya Chen"},
        })
        user_id = resp.user.id

        # Seed user_profiles + user_platforms
        self.sb.table("user_profiles").upsert({
            "user_id": user_id,
            "display_name": "Maya Chen",
            "headline": "Freelancer · Email Automation & Web Scraping",
            "avatar_url": "",
            "is_public": True,
        }, on_conflict="user_id").execute()

        for platform in ["upwork", "fiverr"]:
            self.sb.table("user_platforms").upsert({
                "user_id": user_id,
                "platform": platform,
            }, on_conflict="user_id,platform").execute()

        return user_id

    def _ensure_other_user(self) -> str:
        """Get or create the 'other user' for ownership tests."""
        try:
            users = self.sb.auth.admin.list_users()
            for u in users:
                if u.email == "other@sprint-platform.local":
                    return u.id
        except Exception:
            pass

        resp = self.sb.auth.admin.create_user({
            "email": "other@sprint-platform.local",
            "password": "other-pass-123",
            "email_confirm": True,
            "user_metadata": {"display_name": "Jordan Lee"},
        })
        user_id = resp.user.id

        self.sb.table("user_profiles").upsert({
            "user_id": user_id,
            "display_name": "Jordan Lee",
            "headline": "Freelancer · Web Scraping",
            "avatar_url": "",
            "is_public": True,
        }, on_conflict="user_id").execute()

        return user_id

    def _ensure_admin_user(self) -> str:
        """Get or create the admin user for admin feature tests."""
        try:
            users = self.sb.auth.admin.list_users()
            for u in users:
                if u.email == "admin@sprint-platform.local":
                    return u.id
        except Exception:
            pass

        # Admin user should already exist in Supabase Auth with role=admin
        # This is a fallback - normally it's pre-created
        resp = self.sb.auth.admin.create_user({
            "email": "admin@sprint-platform.local",
            "password": "admin-pass-123",
            "email_confirm": True,
            "user_metadata": {"display_name": "Admin User", "role": "admin"},
        })
        user_id = resp.user.id

        self.sb.table("user_profiles").upsert({
            "user_id": user_id,
            "display_name": "Admin User",
            "headline": "Platform Administrator",
            "avatar_url": "",
            "is_public": False,
        }, on_conflict="user_id").execute()

        return user_id

    def _create_test_user(self, fixture_id: str) -> str:
        """Create a test user for arbitrary fixture ID, or return existing."""
        email = f"{fixture_id.replace('-', '')}@test.sprint-platform.local"
        # Check if user already exists
        try:
            users = self.sb.auth.admin.list_users()
            for u in users:
                if u.email == email:
                    return u.id
        except Exception:
            pass

        resp = self.sb.auth.admin.create_user({
            "email": email,
            "password": "test-pass-123",
            "email_confirm": True,
            "user_metadata": {"display_name": fixture_id.replace("-", " ").title()},
        })
        user_id = resp.user.id
        return user_id

    # ──────────────────────────────────────────────────────────────
    # SPRINT ID MAPPING
    # ──────────────────────────────────────────────────────────────

    def resolve_sprint_id(self, fixture_id: str, cluster_key: str = "email-automation", user_fixture: str = "test-user-123", resolve_only: bool = False) -> str:
        """Map fixture sprint ID to real sprint UUID.

        resolve_only=True: never create — return the fixture id unchanged when no
        mapping/reuse exists (used by the URL rewriter so unknown sprint ids
        reach the route and get the specced 302).
        Every sprint returned (created OR reused) is tracked so cleanup can
        reset/delete it — reused rows must not leak state between scenarios.
        """
        if fixture_id in self._fixture_to_real_sprint:
            return self._fixture_to_real_sprint[fixture_id]

        # resolve_only: only the adapter's mapping is authoritative. Never do the
        # user-scoped reuse lookup here — an unknown fixture id must pass through
        # unchanged so routes return the specced not-found redirect.
        if resolve_only:
            return fixture_id

        user_id = self.resolve_user_id(user_fixture)

        # Check for existing sprint with matching cluster
        existing = self.sb.table("sprints").select("id").eq("user_id", user_id).eq("cluster_key", cluster_key).limit(1).execute().data
        if existing:
            real_id = existing[0]["id"]
            if real_id not in self._created_sprints:
                self._created_sprints.append(real_id)
        else:
            # Create new sprint
            cohort = self.sb.table("cohorts").select("id").eq("cluster_key", cluster_key).eq("status", "active").limit(1).execute().data
            cohort_id = cohort[0]["id"] if cohort else None

            sprint = self.sb.table("sprints").insert({
                "user_id": user_id,
                "cohort_id": cohort_id,
                "cluster_key": cluster_key,
                "phase": "A",
                "current_day": 1,
                "status": "active",
                "proposals_sent": 0,
                "responses_received": 0,
                "interviews_held": 0,
                "offers_received": 0,
                "contracts_won": 0,
                "contracts_completed": 0,
                "total_earned": 0,
                "repeat_clients": 0,
                "is_actively_seeking": True,
            }).execute().data[0]
            real_id = sprint["id"]
            self._created_sprints.append(real_id)

            # Create 14 sprint_days — action_type must mirror the app's
            # sprint_planner.action_for (day 1 = setup, 2-5 copywork, 6-8
            # contract, 9-10 case-study, 11-14 proposal) so the fixture's day
            # content matches what a real enrolled sprint renders.
            from services.sprint_planner import action_for
            phase_map = {d: "A" for d in range(1, 6)} | {d: "B" for d in range(6, 11)} | {d: "C" for d in range(11, 15)}
            for d in range(1, 15):
                phase = phase_map[d]
                action_type = action_for(d)
                self.sb.table("sprint_days").insert({
                    "sprint_id": real_id, "phase": phase, "day_no": d,
                    "title": f"Day {d}", "description": "",
                    "action_type": action_type, "action_payload": {}, "is_done": False,
                }).execute()

            # Create sprint_unlock_snapshots (upsert — reused sprints may already have one)
            self.sb.table("sprint_unlock_snapshots").upsert({
                "sprint_id": real_id, "user_id": user_id,
                "completed_days": 0, "unlocked_count": 0, "total_in_cluster": 0, "last_delta": 0,
            }, on_conflict="sprint_id,user_id").execute()

        self._fixture_to_real_sprint[fixture_id] = real_id
        return real_id

    # ──────────────────────────────────────────────────────────────
    # PROPOSAL ID MAPPING
    # ──────────────────────────────────────────────────────────────

    def resolve_proposal_id(self, fixture_id: str) -> str:
        """Map fixture proposal ID to real UUID, creating if needed."""
        if fixture_id in self._fixture_to_real_proposal:
            return self._fixture_to_real_proposal[fixture_id]
        # If it's already a valid UUID, accept it directly
        if self._is_uuid(fixture_id):
            self._fixture_to_real_proposal[fixture_id] = fixture_id
            return fixture_id
        # Otherwise generate a real UUID and track the mapping
        real_id = str(_uuid.uuid4())
        self._fixture_to_real_proposal[fixture_id] = real_id
        return real_id

    def get_proposal_real_id(self, fixture_id: str) -> str:
        """Look up the real UUID for a fixture proposal ID that was seeded.
        Returns the fixture ID unchanged if no mapping exists (for assertions
        that haven't been resolved yet)."""
        return self._fixture_to_real_proposal.get(fixture_id, fixture_id)

    # ──────────────────────────────────────────────────────────────
    # SEED HELPERS (write-through to live DB)
    # ──────────────────────────────────────────────────────────────

    def seed_table(self, table: str, rows: List[Dict[str, Any]], on_conflict: Optional[str] = None, track_cleanup: bool = True):
        """Seed rows into live DB, optionally track created IDs for cleanup."""
        for row in rows:
            # Resolve fixture IDs in the row (user_id, sprint_id, job_feed_id, etc.)
            row = self._resolve_fixture_ids_in_row(row)

            # Track fixture → real proposal ID mapping for proposals table
            fixture_id = row.get("id") if isinstance(row.get("id"), str) else None
            if table == "proposals" and fixture_id and not self._is_uuid(fixture_id):
                real_id = str(_uuid.uuid4())
                self._fixture_to_real_proposal[fixture_id] = real_id
                row["id"] = real_id
            else:
                # Generate real UUID for id field if it's a fixture ID
                if "id" in row and isinstance(row["id"], str):
                    if not self._is_uuid(row["id"]):
                        row["id"] = str(_uuid.uuid4())

            if on_conflict:
                res = self.sb.table(table).upsert(row, on_conflict=on_conflict).execute()
            else:
                res = self.sb.table(table).insert(row).execute()

            if track_cleanup and res.data:
                created_id = res.data[0].get("id")
                if created_id:
                    self._created_rows.setdefault(table, []).append(created_id)

    def _resolve_fixture_ids_in_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Replace fixture user_id, sprint_id, cluster_key with real UUIDs."""
        new_row = dict(row)

        # user_id
        if "user_id" in new_row and isinstance(new_row["user_id"], str):
            if not self._is_uuid(new_row["user_id"]):
                new_row["user_id"] = self.resolve_user_id(new_row["user_id"])

        # sprint_id
        if "sprint_id" in new_row and isinstance(new_row["sprint_id"], str):
            if not self._is_uuid(new_row["sprint_id"]):
                # Try to extract cluster from the fixture sprint ID
                cluster = "email-automation"
                if "web-scraping" in new_row["sprint_id"]:
                    cluster = "web-scraping"
                elif "ai-chatbots" in new_row["sprint_id"]:
                    cluster = "ai-chatbots"
                new_row["sprint_id"] = self.resolve_sprint_id(new_row["sprint_id"], cluster)

        # job_feed_id - map fixture IDs like "email-automation-1" to real UUIDs
        for key in ("job_feed_id",):
            if key in new_row and isinstance(new_row[key], str):
                if not self._is_uuid(new_row[key]):
                    real_id = get_static_job_id(new_row[key])
                    if real_id != new_row[key]:
                        new_row[key] = real_id

        # cluster_key stays as string (not a UUID)

        return new_row

    @staticmethod
    def _is_uuid(s: str) -> bool:
        """Check if string is a valid UUID."""
        try:
            uuid.UUID(s)
            return True
        except ValueError:
            return False

    # ──────────────────────────────────────────────────────────────
    # CLEANUP (FK-safe order)
    # ──────────────────────────────────────────────────────────────

    def cleanup_scenario(self):
        """Delete all rows created during this scenario, in FK-safe order.

        Tracked sprints are deleted (not just reset) so no state leaks between
        scenarios or runs; ON DELETE CASCADE removes their sprint_days,
        unlock snapshots, capstone briefs, proposals, verification reviews,
        case studies, and copy-work projects.
        """
        # Order: children first, parents last (reverse of seed order)
        cleanup_order = [
            "mentor_sessions",
            "verification_reviews",
            "proposals",
            "case_studies",
            "capstone_briefs",
            "copywork_projects",
            "sprint_days",
            "sprint_unlock_snapshots",
            "sprints",
            "user_momentum",
            "user_platforms",
            "user_profiles",
            "badges",
            "contracts",
            "job_feed",
            "demand_snapshots",
            "cohorts",
            "job_clusters",
        ]

        # Tracked sprints (created or reused this scenario) → delete so the
        # next scenario starts clean. Children cascade.
        for sprint_id in self._created_sprints:
            try:
                self.sb.table("sprints").delete().eq("id", sprint_id).execute()
            except Exception as e:
                print(f"Cleanup warning: sprints {sprint_id}: {e}")

        for table in cleanup_order:
            ids = self._created_rows.get(table, [])
            for id_val in ids:
                try:
                    self.sb.table(table).delete().eq("id", id_val).execute()
                except Exception as e:
                    print(f"Cleanup warning: {table} {id_val}: {e}")

        # Clear tracking
        self._created_rows.clear()
        self._created_sprints.clear()
        self._fixture_to_real_sprint.clear()
        self._fixture_to_real_proposal.clear()

    def track_created(self, table: str, row_id: str):
        """Track an externally-created row (e.g. admin API 201) for cleanup."""
        if row_id:
            self._created_rows.setdefault(table, []).append(row_id)

    # ──────────────────────────────────────────────────────────────
    # QUERY HELPERS
    # ──────────────────────────────────────────────────────────────

    def rows(self, table: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Query live DB with optional filters."""
        q = self.sb.table(table).select("*")
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        return q.execute().data or []

    def row(self, table: str, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        rows = self.rows(table, filters)
        return rows[0] if rows else None


@contextmanager
def live_db_context():
    """Context manager for BDD scenarios: yields LiveDBAdapter, cleans up on exit."""
    from app import create_app
    app = create_app()
    with app.app_context():
        sb = get_supabase()
        adapter = LiveDBAdapter(sb)
        try:
            yield adapter
        finally:
            adapter.cleanup_scenario()


# Global adapter instance for step functions
_adapter: Optional[LiveDBAdapter] = None


def get_live_adapter() -> LiveDBAdapter:
    """Get the current scenario's LiveDBAdapter."""
    global _adapter
    if _adapter is None:
        from app import create_app
        app = create_app()
        with app.app_context():
            sb = get_supabase()
            _adapter = LiveDBAdapter(sb)
    return _adapter


def reset_live_adapter():
    """Clean up and reset the global adapter."""
    global _adapter
    if _adapter:
        _adapter.cleanup_scenario()
        _adapter = None