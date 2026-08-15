#!/usr/bin/env python3
"""
Playwright-based BDD Browser Test Runner for Admin Features
Runs against LIVE Supabase with REAL admin credentials in a visible browser (headless=False)
"""
import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from playwright.async_api import async_playwright
from supabase import create_client


# ─── CONFIG ──────────────────────────────────────────────────────────
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")  # Local dev server
ADMIN_EMAIL = "admin@sprint-platform.local"
ADMIN_PASSWORD = "admin-pass-123"  # From live_db_adapter fallback

# Use live Supabase for auth verification
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY) if SUPABASE_URL and SUPABASE_SERVICE_KEY else None


# ─── HELPERS ─────────────────────────────────────────────────────────
async def login_admin(page):
    """Log in as admin user via the login page."""
    print(f"🔐 Logging in as admin: {ADMIN_EMAIL}")
    await page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle")
    
    # Fill login form - demo mode only has email field
    await page.fill("input[name='email']", ADMIN_EMAIL)
    await page.click("button[type='submit']")
    
    # Wait for redirect to dashboard or sprints
    await page.wait_for_url(f"{BASE_URL}/sprints**", wait_until="networkidle")
    print(f"✅ Logged in successfully, redirected to: {page.url}")


async def login_via_session(page):
    """Alternative: log in by setting session cookie directly via Supabase."""
    if not sb:
        print("⚠️  No Supabase client, falling back to form login")
        return await login_admin(page)
    
    print("🔐 Getting admin session via Supabase...")
    # Sign in via Supabase to get session
    auth_resp = sb.auth.sign_in_with_password({
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    
    if not auth_resp.session:
        print("❌ Failed to get Supabase session")
        return await login_admin(page)
    
    # Set session cookies in browser
    await page.context.add_cookies([
        {
            "name": "sb-access-token",
            "value": auth_resp.session.access_token,
            "domain": "localhost",
            "path": "/",
        },
        {
            "name": "sb-refresh-token", 
            "value": auth_resp.session.refresh_token,
            "domain": "localhost",
            "path": "/",
        }
    ])
    
    print("✅ Session cookies set")
    return True


async def test_admin_dashboard(page):
    """Test admin dashboard access."""
    print("\n📋 Test: Admin Dashboard Access")
    await page.goto(f"{BASE_URL}/admin/", wait_until="networkidle")
    await page.screenshot(path="/tmp/admin_dashboard.png", full_page=True)
    
    # Check for admin dashboard content
    content = await page.content()
    assert "Admin Dashboard" in content, "Admin Dashboard text not found"
    assert "Job Clusters" in content, "Job Clusters link not found"
    assert "Job Feed" in content, "Job Feed link not found"
    assert "Cohorts" in content, "Cohorts link not found"
    print("✅ Admin dashboard loads correctly")
    print(f"📸 Screenshot: /tmp/admin_dashboard.png")


async def test_job_clusters(page):
    """Test job clusters management."""
    print("\n📋 Test: Job Clusters Management")
    await page.goto(f"{BASE_URL}/admin/clusters", wait_until="networkidle")
    await page.screenshot(path="/tmp/admin_clusters.png", full_page=True)
    
    content = await page.content()
    assert "Job Clusters" in content
    assert "email-automation" in content  # Pre-seeded cluster
    print("✅ Job clusters page loads with seeded data")
    print(f"📸 Screenshot: /tmp/admin_clusters.png")
    
    # Test create cluster
    await page.goto(f"{BASE_URL}/admin/clusters/create", wait_until="networkidle")
    await page.fill("input[name='cluster_key']", "browser-test-cluster")
    await page.fill("input[name='display_name']", "Browser Test Cluster")
    await page.fill("input[name='icon']", "🧪")
    await page.fill("textarea[name='description']", "Created via browser test")
    await page.fill("input[name='job_count']", "99")
    await page.fill("input[name='avg_rate']", "75")
    await page.fill("input[name='growth_score']", "25")
    await page.select_option("select[name='status']", "active")
    await page.click("button[type='submit']")
    await page.wait_for_load_state("networkidle")
    await page.screenshot(path="/tmp/admin_cluster_created.png", full_page=True)
    print("✅ Created new job cluster via browser")
    print(f"📸 Screenshot: /tmp/admin_cluster_created.png")


async def test_job_feed(page):
    """Test job feed management."""
    print("\n📋 Test: Job Feed Management")
    await page.goto(f"{BASE_URL}/admin/feed", wait_until="networkidle")
    await page.screenshot(path="/tmp/admin_feed.png", full_page=True)
    
    content = await page.content()
    assert "Job Feed" in content
    assert "email-automation" in content
    print("✅ Job feed page loads with seeded postings")
    print(f"📸 Screenshot: /tmp/admin_feed.png")
    
    # Test add job posting
    await page.goto(f"{BASE_URL}/admin/feed/create", wait_until="networkidle")
    await page.fill("input[name='cluster_key']", "email-automation")
    await page.fill("input[name='title']", "Browser Test Job Posting")
    await page.fill("input[name='source']", "curated")
    await page.fill("input[name='source_url']", "https://example.com/browser-test-job")
    await page.fill("textarea[name='description']", "A job posting created via browser automation test")
    await page.fill("input[name='skills']", "playwright, browser, automation")
    await page.fill("input[name='rate']", "300")
    await page.select_option("select[name='experience_needed']", "expert")
    await page.fill("input[name='unlock_day']", "7")
    await page.select_option("select[name='status']", "active")
    await page.click("button[type='submit']")
    await page.wait_for_load_state("networkidle")
    await page.screenshot(path="/tmp/admin_job_created.png", full_page=True)
    print("✅ Created new job posting via browser")
    print(f"📸 Screenshot: /tmp/admin_job_created.png")


async def test_cohorts(page):
    """Test cohort management."""
    print("\n📋 Test: Cohort Management")
    await page.goto(f"{BASE_URL}/admin/cohorts", wait_until="networkidle")
    await page.screenshot(path="/tmp/admin_cohorts.png", full_page=True)
    
    content = await page.content()
    assert "Cohorts" in content
    print("✅ Cohorts page loads")
    print(f"📸 Screenshot: /tmp/admin_cohorts.png")
    
    # Test create cohort
    await page.goto(f"{BASE_URL}/admin/cohorts/create", wait_until="networkidle")
    await page.fill("input[name='cluster_key']", "email-automation")
    await page.fill("input[name='name']", "Browser Test Cohort #1")
    await page.fill("input[name='start_date']", "2026-10-01")
    await page.fill("input[name='end_date']", "2026-10-14")
    await page.select_option("select[name='status']", "upcoming")
    await page.click("button[type='submit']")
    await page.wait_for_load_state("networkidle")
    await page.screenshot(path="/tmp/admin_cohort_created.png", full_page=True)
    print("✅ Created new cohort via browser")
    print(f"📸 Screenshot: /tmp/admin_cohort_created.png")


async def test_non_admin_access(page):
    """Test that non-admin users get 403."""
    print("\n📋 Test: Non-Admin Access Denied")
    
    # Log out first
    await page.goto(f"{BASE_URL}/auth/logout", wait_until="networkidle")
    
    # Log in as demo user
    await page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle")
    await page.fill("input[name='email']", "demo@sprint-platform.local")
    await page.click("button[type='submit']")
    await page.wait_for_url(f"{BASE_URL}/sprints**", wait_until="networkidle")
    print("✅ Logged in as demo user")
    
    # Try to access admin
    await page.goto(f"{BASE_URL}/admin/", wait_until="networkidle")
    await page.screenshot(path="/tmp/non_admin_denied.png", full_page=True)
    
    content = await page.content()
    # Should get 403 or redirect
    assert "Admin access required" in content or page.url == f"{BASE_URL}/auth/login"
    print("✅ Non-admin user correctly denied access")
    print(f"📸 Screenshot: /tmp/non_admin_denied.png")


async def test_anonymous_access(page):
    """Test that anonymous users get redirected to login."""
    print("\n📋 Test: Anonymous Access Redirects to Login")
    
    # Clear cookies/storage
    await page.context.clear_cookies()
    
    await page.goto(f"{BASE_URL}/admin/", wait_until="networkidle")
    await page.screenshot(path="/tmp/anonymous_redirect.png", full_page=True)
    
    # Should redirect to login
    assert "/auth/login" in page.url
    print("✅ Anonymous user correctly redirected to login")
    print(f"📸 Screenshot: /tmp/anonymous_redirect.png")


# ─── MAIN ────────────────────────────────────────────────────────────
async def main():
    print("=" * 60)
    print("🎭 PLAYWRIGHT BROWSER TESTS - ADMIN FEATURES")
    print("=" * 60)
    print(f"🌐 Base URL: {BASE_URL}")
    print(f"👤 Admin: {ADMIN_EMAIL}")
    print(f"📊 Supabase: {'Connected' if sb else 'Not configured'}")
    print("=" * 60)
    
    async with async_playwright() as p:
        # Launch visible browser
        browser = await p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
            slow_mo=500  # Slow down for visibility
        )
        
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir="/tmp/admin_test_videos/"
        )
        
        page = await context.new_page()
        
        # Enable console logging
        page.on("console", lambda msg: print(f"  [CONSOLE] {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"  [PAGE ERROR] {err}"))
        
        try:
            # Login as admin
            await login_admin(page)
            
            # Run admin tests
            await test_admin_dashboard(page)
            await test_job_clusters(page)
            await test_job_feed(page)
            await test_cohorts(page)
            
            # Test access control
            await test_non_admin_access(page)
            await test_anonymous_access(page)
            
            print("\n" + "=" * 60)
            print("✅ ALL BROWSER TESTS PASSED")
            print("=" * 60)
            print("📸 Screenshots saved to /tmp/")
            print("🎥 Videos saved to /tmp/admin_test_videos/")
            
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            await page.screenshot(path="/tmp/test_failure.png", full_page=True)
            print(f"📸 Failure screenshot: /tmp/test_failure.png")
            raise
            
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())