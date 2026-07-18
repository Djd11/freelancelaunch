"""
Visual E2E Test — Launches Chrome on your desktop so you can see it
"""
import asyncio
import os
import sys

# Add web-app to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

BASE = "https://freelancelaunch.onrender.com"
SCREENSHOTS = "/tmp/fl_visual_test"
os.makedirs(SCREENSHOTS, exist_ok=True)


async def run():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        print("🚀 Launching Chrome... (watch your screen!)")
        
        browser = await p.chromium.launch(
            headless=False,          # 👈 VISIBLE browser on your desktop
            args=["--start-maximized", "--no-sandbox"]
        )
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            no_viewport=True
        )
        page = await context.new_page()
        
        # ─── 1. LANDING PAGE ──────────────────────────────
        print("\n📍 Landing page...")
        await page.goto(BASE, wait_until="networkidle")
        await asyncio.sleep(2)
        await page.screenshot(path=f"{SCREENSHOTS}/01-landing.png")
        
        # ─── 2. TOPICS ─────────────────────────────────────
        print("📍 Topics page...")
        await page.goto(f"{BASE}/topics", wait_until="networkidle")
        await asyncio.sleep(2)
        await page.screenshot(path=f"{SCREENSHOTS}/02-topics.png")
        
        # ─── 3. TOPIC DETAIL ───────────────────────────────
        print("📍 Topic detail (Web Scraping)...")
        await page.goto(f"{BASE}/topics/web-scraping-python", wait_until="networkidle")
        await asyncio.sleep(2)
        await page.screenshot(path=f"{SCREENSHOTS}/03-topic-detail.png")
        
        # ─── 4. PRICING ────────────────────────────────────
        print("📍 Pricing page...")
        await page.goto(f"{BASE}/payments/pricing", wait_until="networkidle")
        await asyncio.sleep(2)
        await page.screenshot(path=f"{SCREENSHOTS}/04-pricing.png")
        
        # ─── 5. LOGIN ──────────────────────────────────────
        print("📍 Logging in...")
        await page.goto(f"{BASE}/auth/login", wait_until="networkidle")
        await page.fill("input[name='email']", "chinaindiatesting@gmail.com")
        await page.fill("input[name='password']", "others@2024")
        await page.click("button[type='submit']")
        await asyncio.sleep(3)
        await page.screenshot(path=f"{SCREENSHOTS}/05-dashboard.png")
        
        # ─── 6. PIPELINE ───────────────────────────────────
        print("📍 Pipeline page...")
        await page.goto(f"{BASE}/freelance/pipeline", wait_until="networkidle")
        await asyncio.sleep(2)
        await page.screenshot(path=f"{SCREENSHOTS}/06-pipeline.png")
        
        # ─── 7. ADMIN PRODUCTION ───────────────────────────
        print("📍 Admin production dashboard...")
        await page.goto(f"{BASE}/admin/production", wait_until="networkidle")
        await asyncio.sleep(3)
        await page.screenshot(path=f"{SCREENSHOTS}/07-admin-production.png")
        
        # ─── DONE ──────────────────────────────────────────
        print("\n✅ E2E test complete! Browser will close in 5 seconds...")
        print(f"📸 Screenshots saved to: {SCREENSHOTS}")
        await asyncio.sleep(5)
        await browser.close()
        print("✅ Browser closed.")


if __name__ == "__main__":
    asyncio.run(run())
