Feature: Platform-Aware Curriculum & Contract Landing
  As a user who has chosen a topic
  I want a curriculum that teaches me BOTH the skill AND how to win contracts on my chosen platforms
  So that I can land my first freelance contract faster

  Background:
    Given the curriculum generator API is available
    And I am a logged-in user

  Scenario: CG1 — Generate curriculum for a topic without linked platforms
    Given I am enrolled in "Web Scraping with Python"
    And I have NOT linked any freelance platforms
    When a 30-day curriculum is generated
    Then the curriculum should have exactly 30 days
    And Day 1 should be about HTTP Requests or HTML fundamentals
    And Day 30 should be about job preparation, final project, or portfolio
    And there should be NO platform-specific application days

  Scenario: CG2 — Generate curriculum with Upwork linked
    Given I have linked "Upwork" as a verified platform
    When a 30-day curriculum is generated for "Web Scraping with Python"
    Then the curriculum should have 37 days total (30 skill + 7 Upwork)
    And Day 31 should be "Profile Optimization for Upwork Search"
    And Day 32 should be "Writing Proposals That Convert"
    And Day 33 should be "Pricing Strategy for New Upwork Freelancers"
    And Day 37 should be "Building Job Success Score & Getting Repeat Clients"
    And each Upwork day should have a practice_task and apply_task

  Scenario: CG3 — Generate curriculum with Fiverr linked
    Given I have linked "Fiverr" as a verified platform
    When a 30-day curriculum is generated for "Web Scraping with Python"
    Then the curriculum should have 37 days total (30 skill + 7 Fiverr)
    And Day 31 should be "Fiverr Gig Creation & SEO"
    And Day 33 should be "Buyer Request Mastery"
    And Day 37 should be "Scaling from 1 Gig to 5 Gigs"

  Scenario: CG4 — Generate curriculum with Contra linked
    Given I have linked "Contra" as a verified platform
    When a 30-day curriculum is generated for "Web Scraping with Python"
    Then the curriculum should have 35 days total (30 skill + 5 Contra)
    And Day 31 should be "Portfolio Creation (Contra-Specific)"
    And Day 34 should be "Client Communication & Negotiation"
    And Day 35 should be "Building Long-Term Client Relationships"

  Scenario: CG5 — Multiple platforms ordered by demand priority
    Given I have linked "Fiverr", "Upwork", AND "Contra" as verified platforms
    When a 30-day curriculum is generated for "Web Scraping with Python"
    Then the curriculum should have 49 days total
    And Upwork module should appear FIRST (Days 31-37)
    And Fiverr module should appear SECOND (Days 38-44)
    And Contra module should appear LAST (Days 45-49)

  Scenario: CG6 — Platform days appear after skill days, not mixed
    Given I have linked "Upwork"
    When I view the generated curriculum
    Then Days 1-30 should be all skill training
    And Days 31+ should be all platform application training
    And no skill day should appear after Day 30

  Scenario: DV1 — High demand topic shows enroll option
    Given I search for "web scraping" 
    And the platform demand data shows 247 jobs on Upwork
    When I view the search results
    Then I should see a "Create 30-Day Curriculum" button
    And the demand score should be displayed

  Scenario: DV2 — Low demand topic shows warning
    Given I search for "obscure-niche-xyz"
    And the platform demand score is below 30
    When I view the search results
    Then I should see a "Low demand" warning
    And I should see suggestions for alternative popular topics

  Scenario: DV3 — No demand topic is blocked
    Given I search for "made-up-skill-12345"
    And no platform returns any job data
    When I view the search results
    Then I should see "No freelance demand found"
    And the "Create 30-Day Curriculum" button should NOT appear

  Scenario: PW1 — Upwork proposal writing exercise
    Given I am on Day 32 of my curriculum (Proposal Writing)
    When I view the lesson
    Then I should see a proposal writing exercise
    And the exercise should include a real Upwork-style job description
    And I should be prompted to write a 2-line opening about the CLIENT's problem
    And the lesson should warn: "Don't use AI to write proposals"

  Scenario: PW2 — Fiverr gig creation exercise
    Given I am on Day 31 of my Fiverr curriculum (Gig Creation)
    When I view the lesson
    Then I should see competitor research instructions
    And I should be guided to create title, description, and packages
    And the lesson should emphasize SEO keyword matching

  Scenario: PW3 — Contra portfolio exercise
    Given I am on Day 31 of my Contra curriculum (Portfolio Creation)
    When I view the lesson
    Then I should see the Problem to Approach to Result format
    And I should be asked to create 3 case study drafts

  Scenario: CT1 — Proposal tracked per platform
    Given I have submitted a proposal on Upwork
    When I log it in my pipeline
    Then I should select "Upwork" from the platform dropdown
    And the proposal should be counted in my Upwork stats
    And my total proposals_sent should increment by 1

  Scenario: CT2 — Platform-specific checklist visible
    Given I have linked "Upwork"
    When I view my dashboard
    Then I should see an Upwork profile checklist section
    And the checklist should include "Profile photo", "Title", "Overview", "Portfolio items"
    And I should be able to mark items as complete

  Scenario: CT3 — Contract tracking filtered by platform
    Given I have contracts on both Upwork and Fiverr
    When I view my pipeline page
    Then I should see a platform filter dropdown
    And selecting "Upwork" should show only Upwork contracts
    And selecting "All" should show all contracts

  Scenario: E1 — Platform-linked enrollment without platform days
    Given I have linked "Upwork"
    But the curriculum generator API is unavailable
    When a fallback curriculum is generated
    Then the curriculum should still have 30 skill days
    But NO platform days should be appended (fallback doesn't support it)
    And a warning should be logged

  Scenario: E2 — Invalid platform ignored in curriculum
    Given I have linked "invalid-platform-not-exist"
    When a curriculum is generated
    Then the curriculum should have only 30 skill days
    And the invalid platform should be silently ignored

  Scenario: LS1 — Platform lesson has all required fields
    Given the Upwork module has 7 days
    When I inspect each day
    Then each day should have: title, description, practice_task, apply_task, video_title
    And all fields should be non-empty strings

  Scenario: LS2 — Skill lesson vs platform lesson differentiation
    Given I compare a skill day and a platform day
    Then the skill day's title should contain the technical topic name
    And the platform day's title should contain the platform name
    And the skill day's apply_task should be coding/technical
    And the platform day's apply_task should be about applying/submitting proposals
