#!/usr/bin/env python3
"""Fix: Seed cluster_content_library from admin's existing sprints and create admin user_profiles.

Root cause: cluster_content_library was empty (0 rows) because the admin
had never run content generation, and no seed_from_sprint was called.
Additionally, admin@sprint-platform.local had no user_profiles row.

This script:
1. Seeds cluster_content_library from the admin's existing sprints
2. Creates user_profiles row for the admin user
3. Verifies all clusters have ready library content
"""
import os
import sys
from dotenv import load_dotenv
load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not (url and key):
    sys.exit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

from supabase import create_client
sb = create_client(url, key)

ADMIN_ID = "6056b121-4789-4bd5-ba22-639194314344"
ADMIN_EMAIL = "admin@sprint-platform.local"
CLUSTERS = ["email-automation", "web-scraping", "ai-chatbots"]


def ensure_admin_profile():
    """Create user_profiles row for admin if missing."""
    r = sb.table("user_profiles").select("*").eq("user_id", ADMIN_ID).execute()
    if r.data:
        print(f"Admin user_profiles already exists (id={r.data[0]['user_id'][:8]}...)")
        return True

    # Check if admin exists in auth.users
    users = sb.auth.admin.list_users()
    admin_user = None
    for u in users:
        if u.email == ADMIN_EMAIL:
            admin_user = u
            break

    if not admin_user:
        print("ERROR: Admin user not found in auth.users")
        return False

    sb.table("user_profiles").upsert({
        "user_id": ADMIN_ID,
        "display_name": "Sprint Platform Admin",
        "headline": "Platform Administrator",
        "avatar_url": "",
        "is_public": False,
    }, on_conflict="user_id").execute()
    print(f"Created user_profiles for admin ({ADMIN_ID[:8]}...)")
    return True


def seed_library_from_sprint(cluster_key, sprint_id):
    """Seed cluster_content_library from an existing sprint using content_library.seed_from_sprint."""
    from services.content_library import seed_from_sprint, is_ready, library_status

    # Check if library is already populated
    status = library_status(sb, cluster_key)
    if status["ready"]:
        print(f"  {cluster_key}: library already ready ({status['days']} days, {status['projects']} projects)")
        return True

    # Check if sprint has content to seed
    days = sb.table("sprint_days").select("day_no,action_payload").eq("sprint_id", sprint_id).order("day_no").execute().data
    populated_days = [d for d in days if d.get("action_payload", {}).get("lesson")]

    if not populated_days:
        print(f"  {cluster_key}: sprint {sprint_id[:8]} has no content to seed")
        return False

    print(f"  {cluster_key}: seeding from sprint {sprint_id[:8]} ({len(populated_days)} days with content)")
    copied = seed_from_sprint(sb, cluster_key, sprint_id, overwrite=False)
    print(f"  {cluster_key}: copied {copied['days']} days, {copied['projects']} projects")

    # Verify
    status = library_status(sb, cluster_key)
    if status["ready"]:
        print(f"  {cluster_key}: library is now READY ({status['days']} days, {status['projects']} projects)")
    else:
        print(f"  {cluster_key}: library partial ({status['days']} days, {status['projects']} projects)")
    return status["ready"]


def main():
    print("=== Fix: Seed cluster_content_library and admin profile ===\n")

    # Step 1: Ensure admin profile exists
    print("Step 1: Admin user_profiles")
    if not ensure_admin_profile():
        sys.exit(1)

    # Step 2: Seed library for each cluster from admin's sprints
    print("\nStep 2: Seed cluster_content_library from admin sprints")
    admin_sprints = {s["cluster_key"]: s["id"] for s in sb.table("sprints").select("cluster_key,id").eq("user_id", ADMIN_ID).execute().data}

    all_ready = True
    for cluster_key in CLUSTERS:
        sprint_id = admin_sprints.get(cluster_key)
        if not sprint_id:
            print(f"  {cluster_key}: No admin sprint found")
            all_ready = False
            continue
        ready = seed_library_from_sprint(cluster_key, sprint_id)
        if not ready:
            all_ready = False

    # Step 3: Verify all clusters are ready
    print("\nStep 3: Final verification")
    all_ok = True
    for cluster_key in CLUSTERS:
        from services.content_library import library_status
        status = library_status(sb, cluster_key)
        ready = status["ready"]
        icon = "OK" if ready else "FAIL"
        print(f"  [{icon}] {cluster_key}: {status['days']} days, {status['projects']} projects")
        if not ready:
            all_ok = False

    # Step 4: Set ADMIN_USER_ID in .env if not present
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    with open(env_path, "r") as f:
        env_content = f.read()

    if "ADMIN_USER_ID" not in env_content:
        with open(env_path, "a") as f:
            f.write(f"\n# Admin user ID for admin route authorization\nADMIN_USER_ID={ADMIN_ID}\n")
        print(f"\nStep 4: Added ADMIN_USER_ID={ADMIN_ID} to .env")
    else:
        print("\nStep 4: ADMIN_USER_ID already in .env")

    if all_ok:
        print("\n=== FIX COMPLETE: All clusters have library content ===")
    else:
        print("\n=== FIX PARTIAL: Some clusters may not be fully ready ===")


if __name__ == "__main__":
    main()
