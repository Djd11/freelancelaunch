Feature: Complete Element-by-Element Interaction Audit
#   As a user on any page
#   I want every element to have a clear purpose and correct behavior
#   So that the app is intuitive and useful

#   =============================================================================
#   1. LANDING PAGE
#   =============================================================================

  Scenario: L1 — Hero headline makes value proposition clear
    When I visit /
    Then the hero should show the headline "Pick a skill" 
    And the subtitle should explain the video-first learning model
    And there should be exactly 2 CTAs: "Explore Skills" and "Start Free"
    And "Explore Skills" should navigate to /topics
    And "Start Free" should navigate to /auth/signup
    And both CTAs should be immediately visible without scrolling

  Scenario: L2 — Stats reinforce credibility
    When I view the hero stats
    Then I should see "5 in-demand skills" — tells me breadth
    And I should see "Daily video lessons" — tells me format
    And I should see "Real contract tracking" — tells me outcome

  Scenario: L3 — How It Works (4 steps)
    When I scroll to How It Works
    Then Step 1 "Choose a skill" should explain selection
    And Step 2 "Get your curriculum" should explain personalization
    And Step 3 "Learn daily" should explain the routine
    And Step 4 "Earn" should explain the outcome
    And each step should have a numbered circle or icon

  Scenario: L4 — Topic preview cards are clickable
    When I view the Available Skills section
    Then I should see exactly 5 clickable cards
    And each card should show: icon, name, job count, hourly rate
    And hovering a card should show a visual change
    And clicking navigates to /topics/<slug>

  Scenario: L5 — Dual revenue section
    When I view "Built differently"
    Then "You learn" should describe the learning process
    And "You earn" should describe income tracking
#    ISSUE: "You earn" is vague — should clarify: track proposals, contracts, payments

  Scenario: L6 — Bottom CTA
    When I scroll to the bottom gradient section
    Then "Ready to start?" should lead to /auth/signup
    And "Browse Skills" should lead to /topics
#    ISSUE: Two CTAs pointing to same pages as hero — repetitive but acceptable

#   =============================================================================
#   2. TOPICS EXPLORER
#   =============================================================================

  Scenario: T1 — Search bar is prominent
    When I visit /topics
    Then the search bar should be the first thing below the header
    And its placeholder should say "Search any skill..."
#    ISSUE: Search results show "Create 30-Day Curriculum" button even if user is logged out — should redirect to login first

  Scenario: T2 — Search results include platform data
    When I search for a topic with results
    Then I should see Upwork jobs + rate, Fiverr jobs + rate, Contra jobs + rate
    And I should see a "Create 30-Day Curriculum" button
#    ISSUE: Button text is long — "Create 30-Day Curriculum" should be "Build My Curriculum"
#    ISSUE: No "View on Upwork" direct link per platform

  Scenario: T3 — Topic cards show key data
    When I view the curated grid
    Then each card should show: trend badge, job count, rate, time-to-gig, skills
#    ISSUE: "247 open contracts" is confusing — should say "247 active jobs on Upwork"
#    ISSUE: "3wk to first gig" is unclear — should say "Est. 3 weeks to first contract"

#   =============================================================================
#   3. TOPIC DETAIL
#   =============================================================================

  Scenario: TD1 — Header shows key value prop
    When I visit /topics/<slug>
    Then I should see the topic icon, name, and description
#    ISSUE: The "Get Started Free" button when logged out says nothing about the topic — should say "Start Learning {topic} Free"

  Scenario: TD2 — Demand metrics are clear
    When I view the metric cards
    Then "Open contracts this week" tells current demand
    And "Average freelance rate" tells earning potential
    And "Market demand score" tells viability
#    ISSUE: "Open contracts this week" from WHERE? Upwork? All platforms? Needs source label.

  Scenario: TD3 — Skills section
    When I view the skills tags
    Then each tag represents a skill the user will learn
#    ISSUE: Tags are not clickable — could link to search for that skill

  Scenario: TD4 — Enroll CTA (3 states)
#     State 1 — Logged out: "Get Started Free" → /auth/signup?topic=X
#     State 2 — Logged in, not enrolled: "Start Learning {topic}" → POST to enroll
#     State 3 — Logged in, enrolled: "✅ You're enrolled in {topic}" + "Go to Dashboard →"
#    ISSUE: State 3 has no secondary action — should also show "View My Curriculum" button

  Scenario: TD5 — Curriculum display (3 states)
#     State 1 — Not enrolled: Hardcoded 10-day preview + "Full curriculum unlocks when you enroll"
#     State 2 — Enrolled: Full 30-day curriculum from DB
#     State 3 — Admin: Full curriculum + admin metadata
#     BUG: Fixed — now generates curriculum on enroll ✓

#   =============================================================================
#   4. LOGIN
#   =============================================================================

  Scenario: L1 — Login form
#    ISSUE: No "Forgot password?" link — users will get stuck
#    ISSUE: No way to see password — add show/hide toggle
#    ISSUE: No "Don't have an account?" is present but too small — should be more prominent

#   =============================================================================
#   5. SIGNUP
#   =============================================================================

  Scenario: S1 — Signup form
#    ISSUE: No password strength indicator
#    ISSUE: No terms of service checkbox
#    ISSUE: Name field is optional but labeled as if required
#    ISSUE: No Google/SSO login option (Supabase supports it)

#   =============================================================================
#   6. DASHBOARD
#   =============================================================================

  Scenario: D1 — Main CTA missing
#    ISSUE: The dashboard has NO primary "Start today's lesson" button
#     The checkboxes are good but there should be a prominent "▶ Start Lesson" button above them
#    ISSUE: The video area is empty (gray box) if no video — should show a helpful state

  Scenario: D2 — Progress tracking
#    ISSUE: "X/30 days completed" is good but doesn't show streak
#    ISSUE: The weekly grid shows day numbers only — should show day titles on hover
#    ISSUE: No "View All Days" link to see full curriculum progress

  Scenario: D3 — Pipeline summary card (removed from dashboard)
#    Pipeline was removed from the Dashboard UI — Sprint Track now owns the
#    placement path (proposals, contracts, earnings are tracked there).

  Scenario: D4 — Sidebar quick links
#     "My Portfolio" — useful
#     "Track Applications" — useful  
#     "Upgrade Plan" — useful but oddly placed among utility links
#    ISSUE: No "Browse More Topics" link

#   =============================================================================
#   7. PIPELINE
#   =============================================================================

  Scenario: P1 — Stage progress bar
#    ISSUE: Stage names are not shown on the bar — just "Start → First Contract → Paid"
#     User can't tell what stage "interviewing" or "negotiating" means
#     Should show current stage name prominently

  Scenario: P2 — Stat cards
#    ISSUE: Cards show counts but no trends — "6 proposals sent" but no "vs last week"
#    ISSUE: Clicking a stat card should filter or show details

  Scenario: P3 — Add Contract form
#    ISSUE: Form works but no validation feedback
#    ISSUE: No "client_name" autocomplete from previous clients
#    ISSUE: Platform dropdown is good

#   =============================================================================
#   8. PORTFOLIO
#   =============================================================================

  Scenario: PO1 — Portfolio card display
#    ISSUE: Cards show title, type, day number — but NO preview of content
#    ISSUE: No way to delete a portfolio item
#    ISSUE: No way to feature/badge an item as "Best Work"
#    ISSUE: "+ Add Item" button is good

#   =============================================================================
#   9. SUBMIT DELIVERABLE
#   =============================================================================

  Scenario: SD1 — Submit form
#    ISSUE: Two inputs with name="day_number" (one hidden) — confusing
#    ISSUE: No file upload — users can only paste text
#    ISSUE: "Type" dropdown options are hardcoded — "Blog Post", "Code", "Proposal", etc.
#    ISSUE: No preview before submit

#   =============================================================================
#   10. PRICING
#   =============================================================================

  Scenario: PR1 — Tier comparison
#    ISSUE: All 3 tiers have equal visual weight — only the "MOST POPULAR" badge differentiates
#     Should make "Guided" visually primary, not just via badge
#    ISSUE: Free tier shows "Get Started Free" — but this just goes to signup. Should explain what free includes more clearly.
#    ISSUE: No FAQ section answering "What's the difference?" between tiers

#   =============================================================================
#   11. PROFILE
#   =============================================================================

  Scenario: PRF1 — Profile page
#    ISSUE: Email is shown as disabled input — confusing, just show as text
#    ISSUE: Display name update is the only editable field — very thin page
#    ISSUE: Pipeline stats are good but not clickable — should link to /freelance/pipeline
#    ISSUE: No profile photo upload

#   =============================================================================
#   12. PLATFORM SETUP
#   =============================================================================

  Scenario: PS1 — Platform cards
#    ISSUE: After linking a platform, user sees "⏳ Pending" and deep link button — good
#    ISSUE: But no way to UNLINK a platform (DELETE)
#    ISSUE: "Continue to Dashboard" is the only exit — should also have "Start Learning" if enrolled

#   =============================================================================
#   13. ADMIN
#   =============================================================================

  Scenario: AD1 — Admin dashboard
#    ISSUE: Paid users count always shows 0 — query returns empty
#    ISSUE: "Recent Signups" shows nothing if no signups — should at least show a row count

#   =============================================================================
#   SUMMARY OF ALL ISSUES FOUND
#   =============================================================================

  # | Page | Issue | Priority
#   1 | Topic Detail | "View My Curriculum" button missing for enrolled users | High
#   2 | Dashboard | No "▶ Start Today's Lesson" primary CTA | High
#   3 | Dashboard | Empty video state is confusing | High
#   4 | Pipeline | Stage names not visible on progress bar | Medium
#   5 | Pipeline | Empty pipeline shows "Browse Skills" — should also show "Send First Proposal" | Medium
#   6 | Login | No "Forgot password?" link | Medium
#   7 | Signup | No password strength indicator | Low
#   8 | Portfolio | No delete functionality | Medium
#   9 | Submit | Duplicate day_number input | High
#   10 | Pricing | All tiers equal visual weight | Medium
#   11 | Profile | No photo upload, email as disabled input | Low
#   12 | Platform Setup | No unlink/delete platform option | Medium
#   13 | Topics | "247 open contracts" — from where? Needs source label | Medium
#   14 | Admin | Paid users count broken | Low
