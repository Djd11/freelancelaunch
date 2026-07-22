Feature: Platform-Specific Learning Plans
  As a user enrolled in a skill
  I want a curriculum that teaches me how to WIN contracts on specific platforms
  So that I can apply my skills effectively and get hired

  Background:
    Given I am logged in and have selected a skill
    And I have linked at least one freelance platform (Upwork, Fiverr, or Contra)

  ─── PLATFORM-SPECIFIC CURRICULUM ─────────────────────────

  Scenario: PC1 — Curriculum adapts to linked platforms
    Given I have linked "Upwork" as my platform
    When my curriculum is generated
    Then the curriculum should include 7 days of "Upwork Success" topics
    And Day 1 should be "Profile optimization for Upwork search"
    And Day 4 should be "Pricing strategy for new freelancers"
    And Day 7 should be "Building JSS and getting repeat clients"

  Scenario: PC2 — Fiverr-specific curriculum
    Given I have linked "Fiverr" as my platform
    When my curriculum is generated
    Then the curriculum should include 7 days of "Fiverr Success" topics
    And Day 1 should be "Fiverr gig creation & SEO"
    And Day 3 should be "Buyer request mastery"
    And Day 6 should be "Handling revisions and disputes"

  Scenario: PC3 — Contra-specific curriculum
    Given I have linked "Contra" as my platform
    When my curriculum is generated
    Then the curriculum should include 5 days of "Contra Success" topics
    And Day 1 should be "Portfolio creation (Contra-specific)"
    And Day 5 should be "Building long-term client relationships"

  Scenario: PC4 — Multiple platforms = combined curriculum
    Given I have linked "Upwork" AND "Fiverr"
    When my curriculum is generated
    Then it should include both Upwork and Fiverr success days
    And the total duration should be 30 days (skill) + 14 days (platforms)

  ─── PROPOSAL TRAINING ─────────────────────────────────────

  Scenario: PT1 — Proposal writing module
    Given I have linked "Upwork"
    When I reach Day 2 of the Upwork module
    Then I should see a proposal writing exercise
    And I should see 3 real Upwork job posts to practice on
    And I should be able to submit a proposal draft
    And the system should check for: job reference, specific approach, timeline, price

  Scenario: PT2 — Gig creation module
    Given I have linked "Fiverr"
    When I reach Day 1 of the Fiverr module
    Then I should see a gig creation wizard
    And I should see top 5 competitor gigs in my niche
    And I should be able to draft: title, description, packages, images
    And the system should give SEO suggestions for my gig title

  ─── PLATFORM CHECKLIST ────────────────────────────────────

  Scenario: PCK1 — Upwork profile checklist
    Given I am on the Upwork success module
    When I view the profile checklist
    Then I should see 7 items to complete
    And each item should be a checkbox
    And checking all should mark the module complete

  Scenario: PCK2 — Fiverr success strategy phases
    Given I am on the Fiverr module
    When I view the strategy guide
    Then I should see 3 phases
    And Phase 1 should be "Gig Creation"
    And Phase 2 should be "First 5 Reviews"
    And Phase 3 should be "After 20+ Reviews"
    And each phase should have specific pricing guidance

  ─── ERROR HANDLING ────────────────────────────────────────

  Scenario: E1 — No platform linked
    Given I have not linked any platforms
    When my curriculum is generated
    Then the curriculum should NOT include platform-specific days
    And I should see a prompt: "Link a platform to get platform-specific training"

  Scenario: E2 — All 3 platforms linked
    Given I have linked Upwork, Fiverr, AND Contra
    When my curriculum is generated
    Then all 3 platform modules should be included
    And Upwork should appear first (most job opportunities)
    And Contra should appear last (fewest opportunities)
