"""Visual test: Admin Platform Connections dashboard."""
import asyncio, os, json
os.environ["DEBUG"] = ""

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:5000"
ADMIN_EMAIL = "admin@sprint-platform.local"

async def screenshot(page, name):
    path = f"/tmp/admin_platforms_{name}.png"
    await page.screenshot(path=path, full_page=True)
    print(f"📸 {path}")

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page(viewport={"width": 1280, "height": 900})

        # Step 1: Login
        print("Step 1: Login...")
        await page.goto(f"{BASE}/auth/login", wait_until="domcontentloaded")
        await screenshot(page, "01_login")
        await page.fill("input[name='email']", ADMIN_EMAIL)
        await page.click("button[type='submit']")
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(1)
        print(f"  After login URL: {page.url}")

        # Step 2: Navigate to admin platforms
        print("Step 2: Admin platforms page...")
        await page.goto(f"{BASE}/admin/platforms", wait_until="domcontentloaded")
        await asyncio.sleep(1)
        await screenshot(page, "02_platforms_empty")
        text = await page.inner_text("body")
        print(f"  Has 'No platform connections': {'No platform connections' in text}")

        # Step 3: Fill add platform form (last form on page)
        print("Step 3: Fill add form...")
        forms = page.locator("form")
        count = await forms.count()
        print(f"  Total forms on page: {count}")
        
        # The add form is the one with the ➕ button — it's the last form
        add_form = forms.last
        
        # Verify it has the platform select
        has_select = await add_form.locator("select[name='platform']").count()
        print(f"  Last form has platform select: {has_select > 0}")
        
        if has_select > 0:
            await add_form.locator("select[name='platform']").select_option("rss")
            await add_form.locator("input[name='display_name']").fill("Remote OK - Email Automation Jobs")
            await add_form.locator("textarea[name='feed_urls']").fill("https://remoteok.com/remote-jobs.rss")
            await add_form.locator("input[name='search_query']").fill("email automation")
            await add_form.locator("input[name='cluster_key']").fill("email-automation")
            await screenshot(page, "03_form_filled")

            # Step 4: Submit
            print("Step 4: Submit add form...")
            await add_form.locator("button[type='submit']").click()
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(2)
            await screenshot(page, "04_after_add")
            print(f"  After add URL: {page.url}")

        # Step 5: Verify list
        print("Step 5: Verify platforms list...")
        await page.goto(f"{BASE}/admin/platforms", wait_until="domcontentloaded")
        await asyncio.sleep(1)
        await screenshot(page, "05_platforms_list")
        text = await page.inner_text("body")
        print(f"  Has 'Remote OK': {'Remote OK' in text}")
        print(f"  Has 'Active': {'Active' in text}")
        print(f"  Has 'No platform': {'No platform connections' in text}")

        # Step 6: Trigger refresh
        print("Step 6: Trigger refresh...")
        refresh_form = page.locator("form[action*='refresh_all']")
        if await refresh_form.count() > 0:
            await refresh_form.locator("button[type='submit']").click()
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(2)
            await screenshot(page, "06_after_refresh")
            print(f"  After refresh URL: {page.url}")
            # Get response body
            text = await page.inner_text("body")
            print(f"  Response (first 300 chars): {text[:300]}")

        # Step 7: Final state
        print("Step 7: Final state...")
        await page.goto(f"{BASE}/admin/platforms", wait_until="domcontentloaded")
        await asyncio.sleep(1)
        await screenshot(page, "07_final")
        text = await page.inner_text("body")
        print(f"  Final state: {text[:500]}")

        await browser.close()
        print("\n✅ Done — check /tmp/admin_platforms_*.png")

if __name__ == "__main__":
    asyncio.run(main())
