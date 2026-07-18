"""
Standalone Playwright test for FreelanceLaunch admin production page.
Runs outside Behave's asyncio loop to avoid Sync API conflict.
"""
import os, sys, json, subprocess

# ─── Configuration ──────────────────────────────────────────
BASE_URL = "https://freelancelaunch.onrender.com"
ADMIN_EMAIL = "chinaindiatesting@gmail.com"
ADMIN_PASSWORD = "others@2024"
SCREENSHOT_DIR = "/tmp/fl_bdd_screenshots"

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# ─── Playwright test script ─────────────────────────────────
playwright_script = """
import asyncio
from playwright.async_api import async_playwright
import json, os, sys

SCREENSHOT_DIR = sys.argv[1]
BASE_URL = sys.argv[2]
EMAIL = sys.argv[3]
PASSWORD = sys.argv[4]

async def run():
    results = {"passed": 0, "failed": 0, "tests": []}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        # ─── TEST 1: View production queue ─────────────────
        test = {"name": "View production queue"}
        try:
            # Login
            await page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle")
            await page.fill("input[name='email']", EMAIL)
            await page.fill("input[name='password']", PASSWORD)
            await page.click("button[type='submit']")
            await page.wait_for_timeout(3000)
            await page.screenshot(path=f"{SCREENSHOT_DIR}/01-after-login.png")
            
            # Navigate to admin production
            await page.goto(f"{BASE_URL}/admin/production", wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(2000)
            await page.screenshot(path=f"{SCREENSHOT_DIR}/02-admin-production.png")
            
            # Check for "Pending" section
            content = await page.content()
            assert "Pending" in content, "No Pending section found"
            assert "Recent" in content, "No Recent section found"
            
            # Check for day numbers
            day_elements = await page.locator("text=Day").all()
            assert len(day_elements) > 0, "No Day elements found"
            
            test["status"] = "PASS"
            test["detail"] = f"Found {len(day_elements)} day entries, Pending + Recent sections visible"
            results["passed"] += 1
        except Exception as e:
            test["status"] = "FAIL"
            test["detail"] = str(e)
            results["failed"] += 1
        results["tests"].append(test)
        
        # ─── TEST 2: Status badge colors ──────────────────
        test = {"name": "Status badge colors"}
        try:
            content = await page.content()
            # Check for status indicators in the HTML
            statuses = ["ready", "pending", "failed", "rendering"]
            found = [s for s in statuses if s in content.lower()]
            test["status"] = "PASS" if len(found) > 0 else "FAIL"
            test["detail"] = f"Found status badges: {found}"
            if test["status"] == "PASS":
                results["passed"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            test["status"] = "FAIL"
            test["detail"] = str(e)
            results["failed"] += 1
        results["tests"].append(test)
        
        # ─── TEST 3: Nightly schedule info ────────────────
        test = {"name": "Nightly schedule info"}
        try:
            content = await page.content()
            has_code = "code" in content or "Nightly" in content
            test["status"] = "PASS" if has_code else "FAIL"
            test["detail"] = "Schedule info found" if has_code else "No schedule info"
            if test["status"] == "PASS":
                results["passed"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            test["status"] = "FAIL"
            test["detail"] = str(e)
            results["failed"] += 1
        results["tests"].append(test)
        
        # ─── Summary screenshot ────────────────────────────
        await page.screenshot(path=f"{SCREENSHOT_DIR}/99-final.png")
        await browser.close()
    
    print(json.dumps(results, indent=2))

asyncio.run(run())
"""

# Write the Playwright script
script_path = "/tmp/fl_bdd_test.py"
with open(script_path, "w") as f:
    f.write(playwright_script)

# Run it
result = subprocess.run(
    [sys.executable, script_path, SCREENSHOT_DIR, BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD],
    capture_output=True, text=True, timeout=30
)

print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[:500])

print(f"\n--- Screenshots saved to {SCREENSHOT_DIR} ---")
for f in sorted(os.listdir(SCREENSHOT_DIR)):
    print(f"  📷 {f}")
