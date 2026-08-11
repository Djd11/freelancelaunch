Feature: Complete Page-by-Page Interaction Audit
#   As a user navigating the application
#   I want every element on every page to behave correctly
#   So that the experience is consistent and predictable

#   =============================================================================
#   1. LANDING PAGE (/)
#   =============================================================================

  Scenario: LP-1 — Hero section renders with CTAs
    When I visit the landing page
    Then I should see the hero section with headline "Pick a skill"
    And I should see the subtitle about video-first learning
    And I should see a "Get Started" button in the hero
    And I should see an "Explore Skills" button in the hero
    And clicking "Get Started" takes me to /auth/signup
    And clicking "Explore Skills" takes me to /topics

  Scenario: LP-2 — Stats bar visible below hero
    When I view the landing page
    Then I should see "5 in-demand skills" statistic
    And I should see "Daily video lessons" statistic
    And I should see "Real contract tracking" statistic

  Scenario: LP-3 — How It Works section with 4 steps
    When I scroll to the How It Works section
    Then I should see 4 numbered steps
    And step 1 should be "Choose a skill"
    And step 2 should be "Get your curriculum"
    And step 3 should be "Learn daily"
    And step 4 should be "Earn"

  Scenario: LP-4 — Topics preview shows 5 cards
    When I view the topics preview section
    Then I should see exactly 5 topic preview cards
    And each card should show: icon, name, job count, avg rate
    And clicking any card navigates to /topics/<slug>
    And I should see a "View all topics →" link

  Scenario: LP-5 — Dual Revenue section explains value
    When I view the "Built differently" section
    Then I should see "You learn" card with description
    And I should see "You earn" card with description

  Scenario: LP-6 — Bottom CTA section
    When I scroll to the bottom CTA
    Then I should see "Ready to start?" heading
    And I should see a "Get Started Free" button
    And I should see a "Browse Skills" button
    And clicking either navigates to /auth/signup or /topics

  Scenario: LP-7 — Navigation bar (logged out)
    When I view the nav bar while logged out
    Then I should see "FreelanceLaunch" logo linking to /
    And I should see "Topics" link
    And I should see "Sign in" link
    And I should see "Get Started" button
    And no avatar/user menu should be visible

  Scenario: LP-8 — Footer links
    When I scroll to the footer
    Then I should see "FreelanceLaunch" brand text
    And I should see tagline "Learn a skill. Land a client. Earn your freedom."
    And I should see "Topics" link pointing to /topics
    And I should see "Pricing" link pointing to /payments/pricing

#   =============================================================================
#   2. TOPICS EXPLORER (/topics)
#   =============================================================================

  Scenario: TE-1 — Page header with search
    When I visit /topics
    Then I should see page title "Explore Skills"
    And I should see a search input with placeholder "Search any skill"
    And I should see a "Search" button

  Scenario: TE-2 — Search filters cards live
    When I type "web" in the search box
    Then "Web Scraping with Python" card should remain visible
    And "n8n Automation" card should be hidden
    And "SEO Content Writing" card should be hidden
    And clearing the search should show all cards again

  Scenario: TE-3 — Search returns platform demand data
    When I type "python" and click Search
    Then search results section should appear
    And I should see platform data for Upwork (jobs + rate)
    And I should see platform data for Fiverr (jobs + rate)
    And I should see platform data for Contra (jobs + rate)
    And I should see a "Create 30-Day Curriculum" button
    And clicking it should POST to /enroll/new

  Scenario: TE-4 — Search shows demand score and insights
    When I search for a topic
    Then I should see demand score out of 100
    And I should see trend (Growing or Stable)
    And I should see difficulty level
    And I should see estimated time to first gig

  Scenario: TE-5 — Search without platforms linked shows prompt
    Given I have not linked any freelance platforms
    When I search for a topic
    Then I should see "Link your platforms to see live demand data"
    And I should see a "Link Platforms" button
    And clicking it navigates to /platforms/setup

  Scenario: TE-6 — Curated topics grid (default view)
    When I first load the topics page (no search)
    Then I should see 5 curated topic cards
    And each card should show:
      | icon | name | trend badge | job count | avg rate | weeks to first gig | skills tags |
    And clicking any card navigates to /topics/<slug>

  Scenario: TE-7 — Topic card hover effects
    When I hover over a topic card
    Then the card should have a hover border color change
    And the topic name should change to indigo color

  Scenario: TE-8 — No results state
    When I search for "zzzxyznonexistent"
    Then the curated grid should show all cards filtered to none
    And the search results section should show no platform data or "No demand found"

  Scenario: TE-9 — Demand data disclaimer
    When I view the topics page
    Then I should see "Demand data updated weekly from Upwork and Fiverr"
    And I should see "Skills with 80+ demand score are verified"

#   =============================================================================
#   3. TOPIC DETAIL (/topics/<slug>)
#   =============================================================================

  Scenario: TD-1 — Header with icon, name, trend, description
    When I visit /topics/web-scraping-python
    Then I should see the topic icon rendered
    And I should see the full topic name
    And I should see the trend badge (Growing/Stable)
    And I should see the full description text

  Scenario: TD-2 — Three demand metric cards
    When I view the topic detail
    Then I should see "Open contracts this week" with job count
    And I should see "Average freelance rate" with $ rate
    And I should see "Market demand score" with score out of 100

  Scenario: TD-3 — Skills tags displayed
    When I view the topic detail
    Then I should see 5 skill tags
    And each tag should be clickable (style only)
    And tags should match the topic's skills array

  Scenario: TD-4 — Outcomes and difficulty
    When I view the topic detail
    Then I should see the outcomes text in amber card
    And I should see difficulty level
    And I should see estimated time to first gig

  Scenario: TD-5a — Enroll button (logged out)
    Given I am logged out
    When I view the topic detail
    Then I should see "Get Started Free" button
    And clicking it navigates to /auth/signup?topic=<slug>
    And I should see "Sign in" link below

  Scenario: TD-5b — Enroll button (logged in, not enrolled)
    Given I am logged in but not enrolled
    When I view the topic detail
    Then I should see "Start Learning {topic}" button
    And clicking it POSTs to /topics/<slug>/enroll
    And I should see "Free tier includes full curriculum" below

  Scenario: TD-5c — Enrolled state (logged in, enrolled)
    Given I am logged in and enrolled
    When I view the topic detail
    Then I should see "You're enrolled" message in green
    And I should see "Go to Dashboard →" link
    And clicking it navigates to /dashboard/

  Scenario: TD-6a — Curriculum section (enrolled)
    Given I am enrolled
    When I view the curriculum section
    Then I should see "Full Curriculum (X days)" heading
    And I should see all 30+ days from the database
    And each day should show: title, day number, practice task preview
    And I should NOT see "Full curriculum unlocks when you enroll"

  Scenario: TD-6b — Curriculum section (not enrolled)
    Given I am not enrolled
    When I view the curriculum section
    Then I should see "What you'll learn (30 days)" heading
    And I should see exactly 10 preview days with hardcoded titles
    And I should see "Full curriculum unlocks when you enroll"

  Scenario: TD-6c — Curriculum section (admin view)
    Given I am logged in as admin (even if not enrolled)
    When I view the curriculum section
    Then I should see "👑 Admin View" badge in the header
    And I should see all curriculum days from the database
    And each day should show character count for practice task
    And I should see admin dashboard link

#   =============================================================================
#   4. AUTH PAGES
#   =============================================================================

  Scenario: AU-1 — Login page form
    When I visit /auth/login
    Then I should see email input with placeholder
    And I should see password input with placeholder
    And I should see "Sign In" submit button
    And I should see "Create one" link to /auth/signup

  Scenario: AU-2 — Login success
    When I submit valid credentials
    Then I should be redirected to /dashboard/
    And I should see "Welcome back!" flash message
    And the nav should show my avatar and menu items

  Scenario: AU-3 — Login failure
    When I submit invalid credentials
    Then I should stay on /auth/login
    And I should see "Login failed: Invalid email or password"
    And the form should retain the email value

  Scenario: AU-4 — Signup page form
    When I visit /auth/signup
    Then I should see name input
    And I should see email input
    And I should see password input (min 6 chars)
    And I should see "Create Free Account" button
    And I should see "Login" link to /auth/login

  Scenario: AU-5 — Signup with topic parameter
    When I visit /auth/signup?topic=web-scraping-python
    Then a hidden topic input should exist with that value
    And submitting creates pipeline with that topic

  Scenario: AU-6 — Signup duplicate email
    When I submit signup with an existing email
    Then I should see "This email is already registered"
    And I should stay on /auth/signup

  Scenario: AU-7 — Logout
    Given I am logged in
    When I click "Sign out" from the dropdown
    Then my session should be cleared
    And I should be redirected to /topics
    And the nav should show "Sign in" again
    And visiting /dashboard/ should redirect to /auth/login

#   =============================================================================
#   5. DASHBOARD (/dashboard/)
#   =============================================================================

  Scenario: DB-1 — Header with cohort info
    Given I am logged in and enrolled
    When I visit /dashboard/
    Then I should see cohort name
    And I should see "Day X of 30" text
    And I should see "X/30 days completed" with progress bar

  Scenario: DB-2 — Video player area
    When I view the dashboard
    Then I should see "Day X: Title" heading
    And if video exists: YouTube embed iframe
    And if video pending: "Today's video is being created" message
    And if no video: "Welcome to FreelanceLaunch" message

  Scenario: DB-3 — Progress checklist (3 items)
    When I view the progress section
    Then I should see "Watch today's video" checkbox
    And I should see "Complete practice task" checkbox
    And I should see "Submit your work" checkbox
    And checking a checkbox should POST to /api/progress/mark
    And checked items should show green border and bg

  Scenario: DB-4 — Submit Deliverable button
    When I view the dashboard
    Then I should see "Submit Deliverable →" button
    And clicking it navigates to /deliverables/submit?day=X
#     Where X is the current day number

  Scenario: DB-5 — Sprint Track hero CTA (replaces the removed Pipeline card)
    When I view the dashboard
    Then I should see "Sprint Track" card
    And I should see "14-day placement" badge
    And I should see "Open Sprint Track →" link
    And clicking it navigates to /sprints

  Scenario: DB-6 — Weekly progress grid
    When I view the "This Week" section
    Then I should see 7 day boxes
    And completed days should have gradient fill
    And current day should have indigo ring
    And future days should be gray

  Scenario: DB-7 — Quick Links section (no Pipeline link)
    When I view the sidebar
    Then I should see "My Portfolio" link
    And I should see "Sprint Track" link
    And I should not see "Track Applications" link
    And I should see "Upgrade Plan" link

  Scenario: DB-8 — Platform banner (if platforms not linked)
    Given I have not linked any platforms
    When I view any page
    Then I should see a purple banner at the top
#     With text "Link your freelance platforms"
    And a "Set up now →" button
    And clicking it navigates to /platforms/setup

#   =============================================================================
#   6. PIPELINE (/freelance/pipeline)
#   =============================================================================

  Scenario: PL-1 — Pipeline stats and stage
    Given I have an active pipeline
    When I visit /freelance/pipeline
    Then I should see the topic name
    And I should see the current stage badge (color-coded)
    And I should see the 8-segment stage progress bar
    And completed stages should be gradient filled
    And future stages should be gray

  Scenario: PL-2 — Four stat cards
    When I view the pipeline
    Then I should see "Sent" card with proposals count
    And I should see "Replies" card with responses count
    And I should see "Interviews" card with interviews count
    And I should see "Contracts" card with contracts count

  Scenario: PL-3 — Earnings display
    When I have earnings > 0
    Then I should see "💰 $X earned" in green

  Scenario: PL-4 — Quick action buttons
    When I view the pipeline
    Then I should see "+1 Proposal Sent" button
    And clicking it increments proposals_sent
    And I should see "I'm Applying Now" button
    And clicking it changes stage to "applying"

  Scenario: PL-5 — Contract form (won a contract)
    When I view the sidebar
    Then I should see "Won a Contract?" card
    And I should see platform dropdown (Upwork/Fiverr/Contra/Direct)
    And I should see client name input (required)
    And I should see project title input (required)
    And I should see contract value input (optional)
    And I should see hours worked input (optional)
    And I should see "+ Add Contract" button
    And submitting creates a contract record

  Scenario: PL-6 — Contract history table
    Given I have completed contracts
    When I view the pipeline
    Then I should see "Contract History" table
#     With columns: Client, Project, Platform, Value, Status
    And status badges should be color-coded (green=completed, blue=active)

  Scenario: PL-7 — Empty pipeline state
    Given I have no pipeline entries
    When I visit /freelance/pipeline
    Then I should see "No active pipeline" message
    And I should see "Browse Skills" button

#   =============================================================================
#   7. PORTFOLIO (/deliverables/portfolio)
#   =============================================================================

  Scenario: PF-1 — Portfolio with items
    Given I have submitted deliverables
    When I visit /deliverables/portfolio
    Then I should see "My Portfolio" heading
    And I should see deliverable cards with: title, type badge, day number, date, content preview
    And I should see "+ Add Item" button

  Scenario: PF-2 — Empty portfolio
    Given I have no deliverables
    When I visit /deliverables/portfolio
    Then I should see "No portfolio items yet"
    And I should see "Submit Your First Piece" button
    And clicking it navigates to /deliverables/submit

#   =============================================================================
#   8. SUBMIT DELIVERABLE (/deliverables/submit)
#   =============================================================================

  Scenario: SD-1 — Form fields
    When I visit /deliverables/submit
    Then I should see "← Back to Dashboard" link
    And I should see day number input (1-60)
    And I should see type dropdown with 5 options
    And I should see title input
    And I should see content textarea
    And I should see "Submit for Portfolio" button

  Scenario: SD-2 — Successful submission
    When I fill all fields and submit
    Then a deliverable record should be created
    And I should be redirected to /dashboard/
    And I should see "Deliverable submitted" flash

#   =============================================================================
#   9. PRICING (/payments/pricing)
#   =============================================================================

  Scenario: PR-1 — Three tier cards
    When I visit /payments/pricing
    Then I should see "Free" tier with 3 features
    And I should see "Guided Accelerator" with "MOST POPULAR" badge at $49
    And I should see "Placement Program" at $199
    And each tier should list its features with checkmarks

  Scenario: PR-2 — Free tier button
    When I am logged out and view pricing
    Then Free tier shows "Get Started Free" → /auth/signup
    When I am logged in and view pricing
    Then Free tier shows "Get Started Free" → /auth/signup

  Scenario: PR-3 — Paid tier buttons
    When I am logged out and view pricing
    Then paid tiers show "Sign Up to Upgrade" → /auth/signup
    When I am logged in and view pricing
    Then paid tiers show "Upgrade" → POST /payments/create-checkout

#   =============================================================================
#   10. PROFILE (/auth/profile)
#   =============================================================================

  Scenario: PRF-1 — Profile form
    Given I am logged in
    When I visit /auth/profile
    Then I should see display name input with current value
    And I should see email (disabled, non-editable)
    And I should see current tier badge
    And I should see "Save" button

  Scenario: PRF-2 — Update display name
    When I change display name and click Save
    Then the user_profiles.display_name should update
    And I should see "Profile updated" flash

  Scenario: PRF-3 — Pipeline summary on profile
    Given I have pipeline data
    When I view profile
    Then I should see 4 stat cards: proposals, contracts, earned, stage

#   =============================================================================
#   11. PLATFORM SETUP (/platforms/setup)
#   =============================================================================

  Scenario: PS-1 — Three platform cards
    Given I am logged in
    When I visit /platforms/setup
    Then I should see Upwork card with 💼 icon and about text
    And I should see Fiverr card with 🎯 icon and about text
    And I should see Contra card with ⚡ icon and about text
    And each card should show current status badge

  Scenario: PS-2 — Link platform flow
    When I click "+ Link Upwork"
    Then the card should update to "⏳ Pending" state
    And I should see a deep link button "Create Upwork Account"
    And clicking it should open upwork.com/signup in new tab
    And I should see a collapsible step-by-step guide
    And I should see "✅ I've done this" button
    And I should see "Skip for now" button

  Scenario: PS-3 — Verify platform
    When I click "✅ I've done this"
    Then the status should update to "✅ Verified"
    And the card should show green verified state

  Scenario: PS-4 — Progress bar
    When I view the setup page
    Then I should see progress bar showing X/3 linked
    And the label should update as platforms are verified

  Scenario: PS-5 — Continue to dashboard
    When I view the setup page
    Then I should see "Continue to Dashboard →" button
    And clicking it navigates to /dashboard/

#   =============================================================================
#   12. ADMIN DASHBOARD (/admin/)
#   =============================================================================

  Scenario: AD-1 — Three stat cards
    Given I am logged in as admin
    When I visit /admin/
    Then I should see "Total Users" card with count
    And I should see "Cohorts" card with count
    And I should see "Paid Users" card with count

  Scenario: AD-2 — Recent signups list
    When I view the admin dashboard
    Then I should see "Recent Signups" section
    And each entry shows source and topic

  Scenario: AD-3 — Active cohorts list
    When I view the admin dashboard
    Then I should see "Active Cohorts" section
    And each entry shows cohort name and day progress

  Scenario: AD-4 — Admin navigation links
    When I view the admin dashboard
    Then I should see "View All Users" link → /admin/users
    And I should see "Production Queue" link → /admin/production

#   =============================================================================
#   13. ADMIN USERS (/admin/users)
#   =============================================================================

  Scenario: AU-1 — Users table
    When I visit /admin/users
    Then I should see "← Admin Home" link
    And I should see a table with: Name, Tier, Topic, Cohort, Created
    And tier badges should be color-coded

#   =============================================================================
#   14. ADMIN PRODUCTION (/admin/production)
#   =============================================================================

  Scenario: AP-1 — Pending queue
    When I visit /admin/production
    Then I should see "Pending" section
    And each pending video shows day number and title
    And each has a "Produce Now" button

  Scenario: AP-2 — Recent productions
    When I visit /admin/production
    Then I should see "Recent" section
    And each entry shows day, title, and status badge
    And status badges are color-coded (green=ready, red=failed)

  Scenario: AP-3 — Nightly schedule info
    When I view the production page
    Then I should see "Nightly Schedule" section
#     With the cron command displayed
    And a manual run command

#   =============================================================================
#   15. NAVIGATION BAR (persistent across all pages when logged in)
#   =============================================================================

  Scenario: NV-1 — Nav links (logged in)
    Given I am logged in
    When I view any page
    Then the nav should show: Logo, Topics, Dashboard, Sprint Track, Pricing, Platform badge, Avatar dropdown
    And clicking Logo → /
    And clicking Topics → /topics
    And clicking Dashboard → /dashboard/
    And clicking Sprint Track → /sprints
    And clicking Pricing → /payments/pricing
    And clicking Platform badge → /platforms/setup

  Scenario: NV-2 — Avatar dropdown menu
    When I click the avatar circle
    Then I should see dropdown with: Profile, Link Platforms, Portfolio, Sign out
    And clicking Profile → /auth/profile
    And clicking Link Platforms → /platforms/setup
    And clicking Portfolio → /deliverables/portfolio
    And clicking Sign out → /auth/logout

  Scenario: NV-3 — Platform badge states
    Given I have no platforms linked
    Then the platform badge should be amber with "Link Platforms"
    Given I have at least one platform linked
    Then the platform badge should be green with "Platforms" and a count

#   =============================================================================
#   16. ERROR & EDGE CASES
#   =============================================================================

  Scenario: ERR-1 — 404 page
    When I visit /nonexistent-page
    Then I should receive a 404 response
    And the app should not crash (no 500)

  Scenario: ERR-2 — Protected routes redirect to login
    When I visit /dashboard/ without being logged in
    Then I should be redirected to /auth/login?next=/dashboard/

  Scenario: ERR-3 — Enroll without login redirects
    When I POST to /topics/<slug>/enroll without being logged in
    Then I should be redirected to /auth/login
    And no enroll should happen

  Scenario: ERR-4 — Submit without login redirects
    When I visit /deliverables/submit without being logged in
    Then I should be redirected to /auth/login
