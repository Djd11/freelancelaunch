#!/usr/bin/env python3
"""
Comprehensive Visual UI/UX Test - walks through the entire user journey
and captures screenshots of every page for visual inspection.
"""
import asyncio
from playwright.async_api import async_playwright
import os

BASE_URL = "http://localhost:5000"
ADMIN_EMAIL = "admin@sprint-platform.local"
ADMIN_PASSWORD = "admin-pass-123"
SCREENSHOT_DIR = "/tmp/ui_ux_test_screenshots"

async def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

async def login_admin(page):
    """Log in as admin user."""
    print("🔐 Logging in as admin...")
    await page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle")
    await page.fill("input[name='email']", ADMIN_EMAIL)
    await page.click("button[type='submit']")
    await page.wait_for_url(f"{BASE_URL}/sprints**", wait_until="networkidle")
    print(f"✅ Logged in, redirected to: {page.url}")

async def login_demo(page):
    """Log in as demo user."""
    print("🔐 Logging in as demo user...")
    await page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle")
    await page.fill("input[name='email']", "demo@sprint-platform.local")
    await page.click("button[type='submit']")
    await page.wait_for_url(f"{BASE_URL}/sprints**", wait_until="networkidle")
    print(f"✅ Logged in as demo")

async def capture(page, name, full_page=True):
    """Capture a screenshot."""
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    await page.screenshot(path=path, full_page=full_page)
    print(f"📸 Screenshot: {path}")
    return path

async def test_landing_page(page):
    """Test the landing page (public)."""
    print("\n📋 Test: Landing Page")
    await page.goto(f"{BASE_URL}/", wait_until="networkidle")
    await capture(page, "01_landing_page")
    
    # Check key elements
    content = await page.content()
    assert "Stop learning skills" in content, "Missing headline"
    assert "Start landing clients" in content, "Missing sub-headline"
    assert "450" in content, "Missing demand counter"
    assert "Demand-Validated" in content, "Missing badge"
    print("✅ Landing page elements verified")

async def test_sprint_picker(page):
    """Test the sprint picker page."""
    print("\n📋 Test: Sprint Picker")
    await page.goto(f"{BASE_URL}/sprints", wait_until="networkidle")
    await capture(page, "02_sprint_picker")
    
    content = await page.content()
    assert "Choose your sprint" in content
    assert "Email Automation" in content
    assert "Web Scraping" in content
    assert "AI Chatbots" in content
    assert "450 jobs open" in content
    assert "Start sprint" in content
    print("✅ Sprint picker elements verified")

async def test_sprint_dashboard(page):
    """Test the sprint dashboard."""
    print("\n📋 Test: Sprint Dashboard")
    await page.goto(f"{BASE_URL}/sprints/efb7e1b7-4662-4da4-8837-cef0aaca5c4d", wait_until="networkidle")
    await capture(page, "03_sprint_dashboard")
    
    content = await page.content()
    assert "Email Automation Sprint" in content
    assert "Day 4" in content
    assert "Phase A" in content
    assert "Job Unlock Meter" in content
    assert "186" in content
    assert "450" in content
    assert "Momentum" in content
    assert "Today" in content
    print("✅ Sprint dashboard elements verified")

async def test_day_view(page):
    """Test the day view page."""
    print("\n📋 Test: Day View (Day 4)")
    await page.goto(f"{BASE_URL}/sprints/efb7e1b7-4662-4da4-8837-cef0aaca5c4d/day/4", wait_until="networkidle")
    await capture(page, "04_day_view")
    
    content = await page.content()
    assert "Day 4" in content
    assert "Copywork" in content
    assert "Abandoned Cart Recovery" in content
    assert "Watch" in content
    assert "Replicate" in content
    assert "Submit for check" in content
    print("✅ Day view elements verified")

async def test_mentor_page(page):
    """Test the AI mentor page."""
    print("\n📋 Test: AI Mentor")
    await page.goto(f"{BASE_URL}/mentor", wait_until="networkidle")
    await capture(page, "05_mentor")
    
    content = await page.content()
    assert "Mentor" in content
    assert "Context" in content
    assert "Ask" in content
    assert "target job" in content
    print("✅ Mentor page elements verified")

async def test_contract_page(page):
    """Test the mock contract page."""
    print("\n📋 Test: Mock Contract")
    await page.goto(f"{BASE_URL}/sprints/efb7e1b7-4662-4da4-8837-cef0aaca5c4d/contract", wait_until="networkidle")
    await capture(page, "06_contract")
    
    content = await page.content()
    assert "Mock Contract" in content
    assert "Client Brief" in content
    assert "REQUIREMENTS" in content
    assert "CONSTRAINTS" in content
    assert "Submit deliverable" in content
    print("✅ Contract page elements verified")

async def test_proposals_page(page):
    """Test the proposals page (Phase C locked)."""
    print("\n📋 Test: Proposals (Phase C Locked)")
    await page.goto(f"{BASE_URL}/sprints/efb7e1b7-4662-4da4-8837-cef0aaca5c4d/proposals", wait_until="networkidle")
    await capture(page, "07_proposals_locked")
    
    content = await page.content()
    assert "Phase C is locked" in content
    assert "Mock Contract" in content
    print("✅ Proposals page (locked) verified")

async def test_profile_page(page):
    """Test the profile page."""
    print("\n📋 Test: Profile Page")
    await page.goto(f"{BASE_URL}/profile/admin", wait_until="networkidle")
    await capture(page, "08_profile")
    
    content = await page.content()
    # Profile page may redirect or show content
    print("✅ Profile page loaded")

async def test_admin_dashboard(page):
    """Test the admin dashboard."""
    print("\n📋 Test: Admin Dashboard")
    await page.goto(f"{BASE_URL}/admin/", wait_until="networkidle")
    await capture(page, "09_admin_dashboard")
    
    content = await page.content()
    assert "Admin Dashboard" in content
    assert "Job Clusters" in content
    assert "Job Feed" in content
    assert "Cohorts" in content
    print("✅ Admin dashboard verified")

async def test_admin_clusters(page):
    """Test admin job clusters."""
    print("\n📋 Test: Admin Job Clusters")
    await page.goto(f"{BASE_URL}/admin/clusters", wait_until="networkidle")
    await capture(page, "10_admin_clusters")
    
    content = await page.content()
    assert "Job Clusters" in content
    assert "email-automation" in content
    print("✅ Admin clusters verified")

async def test_admin_feed(page):
    """Test admin job feed."""
    print("\n📋 Test: Admin Job Feed")
    await page.goto(f"{BASE_URL}/admin/feed", wait_until="networkidle")
    await capture(page, "11_admin_feed")
    
    content = await page.content()
    assert "Job Feed" in content
    print("✅ Admin feed verified")

async def test_admin_cohorts(page):
    """Test admin cohorts."""
    print("\n📋 Test: Admin Cohorts")
    await page.goto(f"{BASE_URL}/admin/cohorts", wait_until="networkidle")
    await capture(page, "12_admin_cohorts")
    
    content = await page.content()
    assert "Cohorts" in content
    print("✅ Admin cohorts verified")

async def test_access_control(page):
    """Test access control - non-admin denied."""
    print("\n📋 Test: Access Control - Non-Admin Denied")
    await page.goto(f"{BASE_URL}/auth/logout", wait_until="networkidle")
    await login_demo(page)
    await page.goto(f"{BASE_URL}/admin/", wait_until="networkidle")
    await capture(page, "13_access_denied")
    
    content = await page.content()
    assert "Admin access required" in content or "/auth/login" in page.url
    print("✅ Access control verified")

async def test_anonymous_redirect(page):
    """Test anonymous user redirect."""
    print("\n📋 Test: Anonymous User Redirect")
    await page.goto(f"{BASE_URL}/auth/logout", wait_until="networkidle")
    await page.goto(f"{BASE_URL}/admin/", wait_until="networkidle")
    await capture(page, "14_anonymous_redirect")
    
    assert "/auth/login" in page.url
    print("✅ Anonymous redirect verified")

async def test_pricing_page(page):
    """Test pricing page."""
    print("\n📋 Test: Pricing Page")
    await page.goto(f"{BASE_URL}/pricing", wait_until="networkidle")
    await capture(page, "15_pricing")
    
    content = await page.content()
    assert "Pricing" in content or "pricing" in content.lower()
    print("✅ Pricing page verified")

async def main():
    await ensure_dir(SCREENSHOT_DIR)
    
    print("=" * 60)
    print("🎭 COMPREHENSIVE VISUAL UI/UX TEST")
    print("=" * 60)
    print(f"🌐 Base URL: {BASE_URL}")
    print(f"📁 Screenshots: {SCREENSHOT_DIR}")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # VISIBLE browser for manual inspection
            args=["--no-sandbox", "--disable-setuid-sandbox"],
            slow_mo=300  # Slow down for visibility
        )
        
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir="/tmp/ui_ux_test_videos/"
        )
        
        page = await context.new_page()
        
        # Enable console logging
        page.on("console", lambda msg: print(f"  [CONSOLE] {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"  [PAGE ERROR] {err}"))
        
        try:
            # Login as admin first
            await login_admin(page)
            
            # Run all visual tests
            await test_landing_page(page)
            await test_sprint_picker(page)
            await test_sprint_dashboard(page)
            await test_day_view(page)
            await test_mentor_page(page)
            await test_contract_page(page)
            await test_proposals_page(page)
            await test_profile_page(page)
            await test_admin_dashboard(page)
            await test_admin_clusters(page)
            await test_admin_feed(page)
            await test_admin_cohorts(page)
            
            # Test access control
            await test_access_control(page)
            await test_anonymous_redirect(page)
            
            # Test pricing
            await test_pricing_page(page)
            
            print("\n" + "=" * 60)
            print("✅ ALL VISUAL TESTS COMPLETED")
            print("=" * 60)
            print(f"📸 Screenshots saved to: {SCREENSHOT_DIR}")
            print(f"🎥 Videos saved to: /tmp/ui_ux_test_videos/")
            
            # List screenshots
            import glob
            screenshots = glob.glob(os.path.join(SCREENSHOT_DIR, "*.png"))
            for s in sorted(screenshots):
                size = os.path.getsize(s) / 1024
                print(f"  {os.path.basename(s)} ({size:.1f} KB)")
            
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            await capture(page, "FAILURE")
            raise
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())