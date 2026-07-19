Feature: Topic Search with Live Platform Data
  As a user
  I want to search for any topic and see live freelance demand data
  So that I can discover new skills with real market opportunity

  Background:
    Given I am logged in
    And I am on the topics explorer page

  ─── SEARCH UI ─────────────────────────────────────────────

  Scenario: S1 — Search bar is visible on topics page
    When I navigate to /topics
    Then I should see a search input with placeholder "Search any skill..."
    And I should see the 5 curated topic cards below it

  Scenario: S2 — Search shows results as I type
    When I type "web" in the search box
    Then the curated topics list should filter to show matching topics
    And "Web Scraping with Python" should be visible
    And "n8n Automation" should be hidden

  ─── LIVE PLATFORM SEARCH ──────────────────────────────────

  Scenario: P1 — Search queries freelance platforms for job data
    When I type "machine learning" in the search box
    And I press Enter or click the search button
    Then the system should search Upwork, Fiverr, and Contra for "machine learning"
    And return job count and average rate per platform
    And display a "Market Demand" card with:
      | Platform   | Jobs | Avg Rate |
      | Upwork     | > 0  | > $0     |
      | Fiverr     | > 0  | > $0     |
      | Contra     | > 0  | > $0     |

  Scenario: P2 — Topic with high demand shows enroll option
    Given I searched for "machine learning" 
    And the platform data shows 50+ jobs
    When I view the results
    Then I should see a "📚 Create 30-Day Curriculum" button
    And clicking it should generate a curriculum and enroll me

  Scenario: P3 — Topic with no demand shows helpful message
    Given I searched for "obscure-niche-12345"
    And no platform returns results
    Then I should see "No freelance demand found for this topic"
    And I should see suggestions for similar popular topics
    And I should see a "Request topic" button

  ─── SEARCH RESULT DETAILS ─────────────────────────────────

  Scenario: D1 — Search result shows platform breakdown
    Given I searched for "python scripting"
    When the results are displayed
    Then I should see a breakdown per platform:
      | Platform  | Detail                     |
      | Upwork    | Jobs: 847, Avg Rate: $35/hr |
      | Fiverr    | Gigs: 1,245, Avg Price: $50 |
      | Contra    | Projects: 112, Avg Rate: $40 |
    And each platform should have a "Visit" link to the actual search page

  Scenario: D2 — Result shows skill insights
    When I view search results for "python scripting"
    Then I should see top related skills: Python, Scripting, Automation, API
    And I should see difficulty level: Beginner-Intermediate
    And I should see estimated time to first gig: 2-3 weeks

  ─── ERROR HANDLING ────────────────────────────────────────

  Scenario: E1 — Platform search timeout shows partial results
    Given Upwork is unreachable but Fiverr responds
    When I search for "data entry"
    Then Fiverr results should display with job count
    And Upwork should show "⚠️ Unable to reach Upwork" 
    And Contra results should display normally

  Scenario: E2 — Empty search shows curated topics
    When I clear the search box
    Then the default 5 curated topics should be displayed
    And the search results section should be hidden

  ─── WHAT HAPPENS WITHOUT LINKED PLATFORMS ─────────────────

  Scenario: W1 — User needs linked platforms to see live data
    Given I have not linked any freelance platforms
    When I search for a topic
    Then I should see a notice: "🔗 Link your platforms to see live demand data"
    And I should see a "Link Platforms" button
    And clicking it takes me to /platforms/setup

  ─── CRUD COVERAGE ────────────────────────────────────────

  # Operation    Component
  # ─────────────────────────────────
  # CREATE       Curriculum generation for new topic (P2)
  # READ         Search results, platform data, market demand (P1, D1, D2)
  # UPDATE       Filter curated list as user types (S2)
  # DELETE       Clear search resets to defaults (E2)
  # Total:       10 scenarios
