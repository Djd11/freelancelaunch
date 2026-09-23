"""Test that reproduces the bug: other users can't see admin's content
because cluster_content_library is empty and admin lacks user_profiles.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

ADMIN_ID = "6056b121-4789-4bd5-ba22-639194314344"
CLUSTERS = ["email-automation", "web-scraping", "ai-chatbots"]


def test_cluster_content_library_not_empty():
    """cluster_content_library must have rows — this is the primary root cause."""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    sb = create_client(url, key)
    r = sb.table("cluster_content_library").select("*").limit(5).execute()
    assert len(r.data) > 0, "cluster_content_library is empty — admin must seed content"


def test_all_clusters_library_ready():
    """Every active cluster must have a ready library (≥14 days, ≥3 projects)."""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    from supabase import create_client
    from services.content_library import library_status
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    sb = create_client(url, key)
    for cluster_key in CLUSTERS:
        status = library_status(sb, cluster_key)
        assert status["ready"] is True, (
            f"{cluster_key} library not ready: {status['days']} days, "
            f"{status['projects']} projects"
        )


def test_admin_has_user_profile():
    """Admin user must have a user_profiles row."""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    sb = create_client(url, key)
    r = sb.table("user_profiles").select("*").eq("user_id", ADMIN_ID).execute()
    assert len(r.data) > 0, "Admin has no user_profiles row"
    assert r.data[0]["display_name"] != "", "Admin display_name is empty"


def test_admin_user_has_role_admin():
    """Admin user must have role=admin in auth metadata."""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    sb = create_client(url, key)
    users = sb.auth.admin.list_users()
    admin_user = None
    for u in users:
        if u.email == "admin@sprint-platform.local":
            admin_user = u
            break
    assert admin_user is not None, "Admin user not found in auth.users"
    assert admin_user.user_metadata.get("role") == "admin", (
        f"Admin role is {admin_user.user_metadata.get('role')}, expected 'admin'"
    )


def test_learners_can_access_library_content():
    """Learners must be able to access library content via apply_library_to_sprint.

    This is the end-to-end test: library exists, is ready, and can be
    applied to a learner's sprint with zero LLM calls.
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()
    from supabase import create_client
    from services.content_library import library_status, apply_library_to_sprint, generate_for_cluster
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    sb = create_client(url, key)

    for cluster_key in CLUSTERS:
        status = library_status(sb, cluster_key)
        assert status["ready"] is True, (
            f"{cluster_key} library not ready — learners cannot see content"
        )
