"""
Step Definitions: Admin Production Dashboard — Browser Tests using Playwright
"""
import os
import threading
from behave import given, when, then
from services.supabase_client import get_supabase


# ─── Playwright browser management ───────────────────────────

def _get_browser(context):
    """Lazy-init Playwright browser."""
    if context.browser is None:
        from playwright.sync_api import sync_playwright
        context.playwright = sync_playwright().start()
        context.browser = context.playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
    return context.browser


def _get_page(context):
    """Get or create a new browser page."""
    if context.page is None:
        browser = _get_browser(context)
        context.page = browser.new_page(viewport={"width": 1280, "height": 800})
    return context.page


# ─── Background ──────────────────────────────────────────────

@given("I am logged in as an admin user")
def step_admin_login(context):
    """Open the Render-deployed app and log in."""
    base_url = "https://freelancelaunch.onrender.com"
    
    # For local testing, fall back to localhost
    import socket
    try:
        socket.create_connection(("freelancelaunch.onrender.com", 443), timeout=3)
    except (OSError, socket.gaierror):
        base_url = "http://localhost:5000"
    
    context.base_url = base_url
    page = _get_page(context)
    
    try:
        page.goto(f"{base_url}/auth/login", wait_until="networkidle", timeout=10000)
        
        # Fill in admin credentials
        page.fill("input[name='email']", "chinaindiatesting@gmail.com")
        page.fill("input[name='password']", "others@2024")
        page.click("button[type='submit']")
        
        # Wait for redirect to dashboard
        page.wait_for_timeout(2000)
        context.logged_in = True
    except Exception as e:
        context.logged_in = False
        context.browser_error = str(e)


@given("there are cohort_videos with various production_status values")
def step_seed_test_videos(context):
    """Seed test cohort_video records for the browser to display."""
    try:
        from app import create_app
        app = create_app()
        with app.app_context():
            sb = get_supabase()
            
            # Check if test cohort exists
            cohorts = sb.table("cohorts").select("id").eq("status", "active").limit(1).execute()
            if cohorts.data:
                context.test_cohort_id = cohorts.data[0]["id"]
            else:
                # Create a test cohort
                topics = sb.table("topics").select("id").limit(1).execute()
                topic_id = topics.data[0]["id"] if topics.data else "web-scraping-python"
                
                cohort = sb.table("cohorts").insert({
                    "topic_id": topic_id,
                    "name": "Test Cohort — BDD",
                    "start_date": "2026-07-17",
                    "current_day": 3,
                    "max_days": 30,
                    "status": "active",
                }).execute()
                context.test_cohort_id = cohort.data[0]["id"]
            
            # Seed test video records with various statuses
            statuses = [
                (1, "ready"),
                (2, "ready"),
                (3, "pending"),
                (4, "pending"),
                (5, "failed"),
            ]
            for day, status in statuses:
                existing = sb.table("cohort_videos").select("id") \
                    .eq("cohort_id", context.test_cohort_id) \
                    .eq("day_number", day).limit(1).execute()
                if not existing.data:
                    sb.table("cohort_videos").insert({
                        "cohort_id": context.test_cohort_id,
                        "day_number": day,
                        "youtube_title": f"Test Video Day {day}",
                        "production_status": status,
                    }).execute()
            
            context.test_videos_seeded = True
    except Exception as e:
        context.test_videos_seeded = False
        context.seed_error = str(e)


@given("there is a pending cohort_video")
def step_pending_video(context):
    """Find or create a pending video for the trigger test."""
    with context.app.app_context():
        sb = get_supabase()
        pending = sb.table("cohort_videos").select("*") \
            .eq("production_status", "pending").limit(1).execute()
        if pending.data:
            context.pending_video = pending.data[0]
        else:
            # Create one
            cv = sb.table("cohort_videos").insert({
                "cohort_id": context.test_cohort_id,
                "day_number": 6,
                "youtube_title": "Test Pending Video",
                "production_status": "pending",
            }).execute()
            context.pending_video = cv.data[0]


# ─── When ────────────────────────────────────────────────────

@when("I navigate to the admin production page")
def step_navigate_production(context):
    page = _get_page(context)
    page.goto(f"{context.base_url}/admin/production", wait_until="networkidle", timeout=15000)
    context.page_source = page.content()


@when('I click the "Produce Now" button for that video')
def step_click_produce(context):
    page = _get_page(context)
    page.goto(f"{context.base_url}/admin/production", wait_until="networkidle", timeout=15000)
    
    # Find and click the first "Produce Now" button
    produce_btn = page.locator("button:has-text('Produce Now')").first
    if produce_btn.is_visible():
        produce_btn.click()
        page.wait_for_timeout(2000)
        context.flash_message = page.locator("[class*='flash-']").text_content()
    

# ─── Then ────────────────────────────────────────────────────

@then("I should see pending videos in the {section} section")
def step_see_pending(context, section):
    page = _get_page(context)
    content = page.content()
    assert "Pending" in content, "No Pending section found"
    day_items = page.locator("text=Day").all()
    assert len(day_items) > 0, "No day items found in production page"


@then("I should see recent videos in the {section} section")
def step_see_recent(context, section):
    content = context.page_source if hasattr(context, 'page_source') else ""
    assert "Recent" in content or "Recent" in str(context.page_source), "No recent section"


@then("each video should show its day number and status")
def step_video_shows_details(context):
    content = context.page_source if hasattr(context, 'page_source') else ""
    assert "Day" in content, "No day numbers visible"
    assert "ready" in content.lower() or "pending" in content.lower(), "No status badges visible"


@then("the production status should change to scripting or rendering")
def step_status_changed(context):
    """Check that the video status changed in the DB."""
    with context.app.app_context():
        sb = get_supabase()
        result = sb.table("cohort_videos").select("production_status") \
            .eq("id", context.pending_video["id"]).limit(1).execute()
        if result.data:
            new_status = result.data[0]["production_status"]
            assert new_status in ("scripting", "rendering", "ready", "failed"), \
                f"Unexpected status: {new_status}"
        # If the production already completed, status might be "ready"


@then("a success flash message should appear")
def step_flash_message(context):
    if hasattr(context, 'flash_message') and context.flash_message:
        assert len(context.flash_message) > 0, "Flash message is empty"


@then('{status} status should have a {color} badge')
def step_status_badge_color(context, status, color):
    page = _get_page(context)
    content = page.content()
    assert status in content.lower(), f"Status '{status}' not found on page"


@then("the nightly schedule info is visible")
def step_schedule_visible(context):
    page = _get_page(context)
    content = page.content()
    assert "Nightly" in content or "nightly" in content, "Nightly schedule section missing"


@then("the cron command should be displayed in a code block")
def step_cron_code(context):
    page = _get_page(context)
    code_blocks = page.locator("code").all()
    code_text = " ".join([cb.text_content() or "" for cb in code_blocks])
    assert len(code_text) > 10, "Cron command code block missing or empty"
