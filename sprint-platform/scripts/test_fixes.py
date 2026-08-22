#!/usr/bin/env python3
"""Visual test: verify RSS feed card + generation banner on sprint dashboard."""
import os, sys, json
from dotenv import load_dotenv
load_dotenv()

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5000"
SCREENSHOTS = "/tmp/test_fixes_screenshots"
os.makedirs(SCREENSHOTS, exist_ok=True)

def get_partial_sprint():
    """Find a sprint that is partially generated (not 14/14)."""
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    sprints = sb.table("sprints").select("id, user_id, status").limit(50).execute().data
    for s in sprints:
        sid = s["id"]
        days = sb.table("sprint_days").select("action_payload") \
            .eq("sprint_id", sid).limit(14).execute().data
        has_content = sum(1 for d in days if (d.get("action_payload") or {}).get("lesson"))
        if 0 < has_content < 14:
            return sid, has_content, len(days)
    return None, 0, 0

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        # Login
        print("1. Logging in...")
        page.goto(f"{BASE}/auth/login")
        page.fill('input[name="email"]', "admin@sprint-platform.local")
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        print(f"   URL: {page.url}")

        # Find a partial sprint
        sid, gen, total = get_partial_sprint()
        if not sid:
            # Check completed sprints
            print("   No partial sprint found, checking all...")
            page.goto(f"{BASE}/sprints")
            page.screenshot(path=f"{SCREENSHOTS}/01_sprint_list.png")
            print(f"   Saved: {SCREENSHOTS}/01_sprint_list.png")
            browser.close()
            return

        print(f"   Found partial sprint: {sid} ({gen}/{total} days)")

        # Visit sprint dashboard
        print("2. Loading sprint dashboard...")
        page.goto(f"{BASE}/sprints/{sid}")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=f"{SCREENSHOTS}/02_dashboard_initial.png", full_page=True)
        print(f"   Saved: {SCREENSHOTS}/02_dashboard_initial.png")

        # Check if generation banner is visible
        banner = page.locator("#gen-banner")
        is_visible = banner.is_visible()
        print(f"3. Generation banner visible: {is_visible}")

        if is_visible:
            banner_text = banner.inner_text()
            print(f"   Banner text: {banner_text[:120]}")

            # Check if retry button exists and is visible
            retry_btn = page.locator("#gen-retry")
            retry_visible = retry_btn.is_visible()
            print(f"   Retry button visible: {retry_visible}")

            if retry_visible:
                # Screenshot before clicking retry
                page.screenshot(path=f"{SCREENSHOTS}/03_before_retry.png", full_page=True)
                print(f"   Saved: {SCREENSHOTS}/03_before_retry.png")

                # Click retry
                print("4. Clicking Retry generation...")
                retry_btn.click()
                page.wait_for_timeout(2000)
                page.screenshot(path=f"{SCREENSHOTS}/04_after_retry_click.png", full_page=True)
                print(f"   Saved: {SCREENSHOTS}/04_after_retry_click.png")

                # Wait and poll for status change
                page.wait_for_timeout(5000)
                page.screenshot(path=f"{SCREENSHOTS}/05_generation_progress.png", full_page=True)
                print(f"   Saved: {SCREENSHOTS}/05_generation_progress.png")
        else:
            print("   Banner is NOT visible (status may be 'partial' → shows quiet bar)")
            # The banner should show as a quiet status bar for partial content
            # Check if gen-banner has any content
            banner_html = banner.inner_html()
            print(f"   Banner HTML length: {len(banner_html)}")

            # Check page content for generation info
            gen_text = page.locator("text=/\\d+ of \\d+ days/").first
            if gen_text.is_visible():
                print(f"   Found status text: {gen_text.inner_text()}")

            # Try to find any "retry" or "generate" buttons
            retry_btns = page.locator("text=/[Rr]etry|[Gg]enerate/")
            count = retry_btns.count()
            print(f"   Found {count} retry/generate buttons")

        # Also test RSS feed card
        print("5. Checking RSS feed card...")
        rss_card = page.locator("text=/Live Job Feed/")
        rss_visible = rss_card.count() > 0 and rss_card.first.is_visible()
        print(f"   RSS Feed card visible: {rss_visible}")

        if rss_visible:
            rss_text = page.locator("#live-jobs-list").inner_text() if page.locator("#live-jobs-list").count() > 0 else "N/A"
            print(f"   RSS entries: {rss_text[:200]}")

        # Check console for JS errors
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.reload()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        if errors:
            print(f"6. JS Errors: {errors}")
        else:
            print("6. No JS errors detected")

        page.screenshot(path=f"{SCREENSHOTS}/06_final.png", full_page=True)
        print(f"   Saved: {SCREENSHOTS}/06_final.png")

        browser.close()
        print(f"\nAll screenshots saved to {SCREENSHOTS}/")

if __name__ == "__main__":
    main()
