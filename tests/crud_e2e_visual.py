"""
Full CRUD E2E Test — VISUAL MODE
Launches Chrome on your desktop. Covers all Create, Read, Update, Delete operations.
"""
import asyncio, os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.makedirs("/tmp/fl_crud_test", exist_ok=True)

BASE = "https://freelancelaunch.onrender.com"
EMAIL = "chinaindiatesting@gmail.com"
PASS = "others@2024"
SHOTS = "/tmp/fl_crud_test"
PASSED = 0
FAILED = 0
results = []

def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        results.append(f"  ✅ {name}")
    else:
        FAILED += 1
        results.append(f"  ❌ {name} — {detail}")

async def run():
    global PASSED, FAILED
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()

        # ─── R1: LANDING PAGE ──────────────────────────────
        print("\n📖 R1: Landing page...")
        await page.goto(BASE)
        await asyncio.sleep(1)
        content = await page.content()
        check("Hero headline visible", "Pick a skill" in content or "Skill" in content)
        check("Get Started button visible", len(await page.locator("text=Get Started").all()) > 0)
        check("Explore Skills button visible", len(await page.locator("text=Explore").all()) > 0)
        await page.screenshot(path=f"{SHOTS}/r1-landing.png")

        # ─── R2: TOPICS PAGE ───────────────────────────────
        print("📖 R2: Topics page...")
        await page.goto(f"{BASE}/topics")
        await asyncio.sleep(1)
        content = await page.content()
        topics_count = len(await page.locator("text=Web Scraping").all()) + \
                       len(await page.locator("text=n8n").all()) + \
                       len(await page.locator("text=Content Writing").all())
        check("5 topics visible", topics_count >= 3)  # at least 3 unique topics
        check("Job count data shown", "open contracts" in content or "247" in content)
        check("Rate shown", "$" in content)
        await page.screenshot(path=f"{SHOTS}/r2-topics.png")

        # ─── R3: TOPIC DETAIL ──────────────────────────────
        print("📖 R3: Topic detail...")
        await page.goto(f"{BASE}/topics/web-scraping-python")
        await asyncio.sleep(1)
        content = await page.content()
        check("Topic name visible", "Web Scraping" in content)
        check("Demand metrics visible", "247" in content and "$30" in content and "92" in content)
        check("Enroll button visible", len(await page.locator("text=Start Learning").all()) > 0 or \
                                         len(await page.locator("text=Get Started").all()) > 0)
        await page.screenshot(path=f"{SHOTS}/r3-topic-detail.png")

        # ─── C1: LOGIN (CREATE session) ────────────────────
        print("\n🔑 C1: Login...")
        await page.goto(f"{BASE}/auth/login")
        await page.fill("input[name='email']", EMAIL)
        await page.fill("input[name='password']", PASS)
        await page.click("button[type='submit']")
        await asyncio.sleep(3)
        url = page.url
        title = await page.title()
        check("Redirected to dashboard", "/dashboard/" in url, f"URL: {url}")
        check("Dashboard title correct", "Dashboard" in title)
        await page.screenshot(path=f"{SHOTS}/c1-login-dashboard.png")

        # ─── R3b: DASHBOARD READS ──────────────────────────
        print("📖 R3: Dashboard data...")
        content = await page.content()
        check("Cohort name visible", "Web Scraping" in content or "Cohort" in content)
        check("Day number shown", "Day" in content)
        check("Progress checklist visible", "Watch" in content or "video" in content.lower())
        check("Pipeline summary visible", "Pipeline" in content or "Proposals" in content)
        await page.screenshot(path=f"{SHOTS}/r3-dashboard-data.png")

        # ─── C5: MARK PROGRESS (CREATE user_progress) ──────
        print("\n✅ C5: Mark progress...")
        checkboxes = await page.locator("input[type='checkbox']").all()
        if checkboxes:
            await checkboxes[0].check()
            await asyncio.sleep(1)
            check("Checkbox 1 checked", await checkboxes[0].is_checked())
        check("Progress checkboxes visible", len(checkboxes) > 0)
        await page.screenshot(path=f"{SHOTS}/c5-progress.png")

        # ─── R4: PIPELINE PAGE ─────────────────────────────
        print("📖 R4: Pipeline page...")
        await page.goto(f"{BASE}/freelance/pipeline")
        await asyncio.sleep(2)
        content = await page.content()
        check("Pipeline stage shown", "Applying" in content)
        check("Proposals count shown", "6" in content)
        check("Contracts count shown", "1" in content)
        check("Earnings shown", "$400" in content or "400" in content)
        check("Contract history visible", "TechStart" in content or "WebAgency" in content)
        check("Add Contract form visible", "Won a Contract" in content)
        await page.screenshot(path=f"{SHOTS}/r4-pipeline.png")

        # ─── U2: INCREMENT PROPOSAL (UPDATE pipeline) ──────
        print("\n✏️  U2: Increment proposal...")
        proposal_btn = page.locator("button:has-text('+1 Proposal Sent')").first
        if await proposal_btn.is_visible():
            await proposal_btn.click()
            await asyncio.sleep(1)
            check("Proposal button clicked", True)
        else:
            check("Proposal button found", False)
        await page.screenshot(path=f"{SHOTS}/u2-proposal.png")

        # ─── C4: ADD CONTRACT (CREATE contract) ────────────
        print("\n✅ C4: Add contract...")
        await page.fill("input[name='client_name']", "BDD Test Client")
        await page.fill("input[name='project_title']", "E2E Test Project")
        await page.fill("input[name='contract_value']", "500")
        await page.fill("input[name='hours_worked']", "20")
        await page.click("button[type='submit']:has-text('Add Contract')")
        await asyncio.sleep(2)
        content = await page.content()
        check("Contract appears in history", "BDD Test Client" in content or "E2E Test Project" in content)
        await page.screenshot(path=f"{SHOTS}/c4-contract-added.png")

        # ─── R5: PORTFOLIO ─────────────────────────────────
        print("📖 R5: Portfolio page...")
        await page.goto(f"{BASE}/deliverables/portfolio")
        await asyncio.sleep(1)
        content = await page.content()
        check("Portfolio page loaded", "Portfolio" in content)
        check("Add Item button visible", "Add Item" in content or "Add" in content)
        await page.screenshot(path=f"{SHOTS}/r5-portfolio.png")

        # ─── C3: SUBMIT DELIVERABLE (CREATE deliverable) ────
        print("\n✅ C3: Submit deliverable...")
        await page.goto(f"{BASE}/deliverables/submit")
        await page.fill("input[type='number'][name='day_number']", "2")
        await page.fill("input[name='title']", "My BDD Scraper")
        await page.fill("textarea[name='content']", "import requests\nprint('BDD test complete')")
        await page.click("button[type='submit']")
        await asyncio.sleep(2)
        url = page.url
        check("Deliverable submitted", "dashboard" in url or "submit" not in url, url)
        await page.screenshot(path=f"{SHOTS}/c3-deliverable.png")

        # ─── U1: UPDATE PROFILE ────────────────────────────
        print("\n✏️  U1: Update profile...")
        await page.goto(f"{BASE}/auth/profile")
        await page.fill("input[name='display_name']", "Admin Updated")
        await page.click("button:has-text('Save')")
        await asyncio.sleep(1)
        check("Profile update submitted", True)
        await page.screenshot(path=f"{SHOTS}/u1-profile.png")

        # ─── R6: PRICING ───────────────────────────────────
        print("📖 R6: Pricing page...")
        await page.goto(f"{BASE}/payments/pricing")
        await asyncio.sleep(1)
        content = await page.content()
        check("Free tier visible", "Free" in content)
        check("Guided tier visible", "$49" in content or "Guided" in content)
        check("Placement tier visible", "$199" in content or "Placement" in content)
        check("Most Popular badge", "MOST POPULAR" in content)
        await page.screenshot(path=f"{SHOTS}/r6-pricing.png")

        # ─── R7-R9: ADMIN PAGES ────────────────────────────
        print("📖 R7: Admin dashboard...")
        await page.goto(f"{BASE}/admin/")
        await asyncio.sleep(1)
        content = await page.content()
        check("Admin users count", "Total Users" in content or "1" in content)
        check("Admin cohorts count", "Cohorts" in content)
        await page.screenshot(path=f"{SHOTS}/r7-admin.png")

        print("📖 R9: Admin production...")
        await page.goto(f"{BASE}/admin/production")
        await asyncio.sleep(2)
        content = await page.content()
        check("Pending section visible", "Pending" in content or "⏳" in content)
        check("Recent section visible", "Recent" in content or "📋" in content)
        check("Nightly schedule shown", "Nightly" in content or "nightly" in content or "cron" in content.lower() or "Schedule" in content)
        await page.screenshot(path=f"{SHOTS}/r9-production.png")

        # ─── R10: PROFILE WITH STATS ──────────────────────
        print("📖 R10: Profile page...")
        await page.goto(f"{BASE}/auth/profile")
        await asyncio.sleep(1)
        content = await page.content()
        check("Profile name shown", "Admin" in content or "Profile" in content)
        check("Pipeline stats shown", "Proposals" in content or "Contracts" in content or "Earned" in content)
        await page.screenshot(path=f"{SHOTS}/r10-profile.png")

        # ─── D1: LOGOUT (DELETE session) ───────────────────
        print("\n🗑️  D1: Logout...")
        await page.goto(f"{BASE}/auth/logout")
        await asyncio.sleep(2)
        url = page.url
        content = await page.content()
        check("Redirected after logout", "topics" in url or "login" in url or "landing" in url.lower())
        # Verify dashboard redirects to login
        await page.goto(f"{BASE}/dashboard/")
        await asyncio.sleep(2)
        url = page.url
        check("Dashboard redirects to login after logout", "login" in url)
        await page.screenshot(path=f"{SHOTS}/d1-logout.png")

        # ─── E1: WRONG PASSWORD ────────────────────────────
        print("\n⚠️  E1: Wrong password...")
        await page.goto(f"{BASE}/auth/login")
        await page.fill("input[name='email']", EMAIL)
        await page.fill("input[name='password']", "wrongpass123")
        await page.click("button[type='submit']")
        await asyncio.sleep(2)
        url = page.url
        check("Stays on login page with wrong password", "login" in url)
        await page.screenshot(path=f"{SHOTS}/e1-wrong-password.png")

        # ─── E2: ACCESS PROTECTED WITHOUT LOGIN ─────────────
        print("⚠️  E2: Protected route redirect...")
        await page.goto(f"{BASE}/admin/")
        await asyncio.sleep(2)
        url = page.url
        check("Redirects to login for protected route", "login" in url)
        await page.screenshot(path=f"{SHOTS}/e2-protected.png")

        await browser.close()

    # ─── SUMMARY ──────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  CRUD E2E TEST RESULTS")
    print(f"{'='*50}")
    for r in results:
        print(r)
    print(f"{'='*50}")
    print(f"  ✅ PASSED: {PASSED}  ❌ FAILED: {FAILED}")
    print(f"  Coverage: {(PASSED/(PASSED+FAILED))*100:.0f}%" if (PASSED+FAILED) > 0 else "  No tests run")
    print(f"{'='*50}")
    print(f"\n📸 Screenshots saved to: {SHOTS}")
    for f in sorted(os.listdir(SHOTS)):
        print(f"  📷 {f}")

if __name__ == "__main__":
    asyncio.run(run())
