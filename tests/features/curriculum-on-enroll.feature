Feature: Curriculum Saved on Enroll
  As a user enrolling in a topic
  I want the full 30-day curriculum to be generated and saved to the database
  So that I can see the actual day-by-day lessons, not hardcoded placeholders

  Background:
    Given the LLM API is available
    And I am a logged-in user

  Scenario: CE1 — Enrolling from topic detail generates curriculum
    Given I am on the topic detail page for "Web Scraping with Python"
    And I am NOT enrolled
    When I click "Start Learning Web Scraping with Python"
    Then my POST to /topics/web-scraping-python/enroll should:
      | action | creates a cohort |
      | action | creates a pipeline entry |
      | action | generates a 30-day curriculum via LLM |
      | action | saves all 30 days to curriculum_days table |
      | action | redirects to /platforms/setup |
    And when I later view the topic detail page
    Then I should see "Full Curriculum (30 days)" heading
    And I should see real day titles (not "Introduction & Setup", "Core Concepts")
    And Day 1 should mention the technical topic

  Scenario: CE2 — Enrolling from search generates curriculum
    Given I search for "Data Analysis"
    And the platform shows demand data
    When I click "Create 30-Day Curriculum for Data Analysis"
    Then my POST to /enroll/new should:
      | action | creates a new topic if needed |
      | action | creates a cohort |
      | action | generates a 30-day curriculum via LLM |
      | action | saves all 30 days to curriculum_days table |
    And when I view the topic detail page
    Then I should see all 30 days from the database

  Scenario: CE3 — Curriculum_days table has correct structure
    Given a curriculum was generated for "Web Scraping with Python"
    When I query the curriculum_days table
    Then I should find exactly 30 rows
    And each row should have:
      | day_number | integer, 1-30, unique per curriculum |
      | title | non-empty string |
      | description | non-empty string |
      | practice_task | non-empty string |
      | apply_task | non-empty string |
      | video_title | non-empty string |
    And day_numbers should be sequential 1, 2, 3...30

  Scenario: CE4 — Enrolled user sees DB curriculum, not hardcoded
    Given I am enrolled in "Web Scraping with Python"
    And curriculum_days exist in the database for this topic
    When I visit /topics/web-scraping-python
    Then I should see "Full Curriculum (30 days)" heading
    And I should NOT see "Full curriculum unlocks when you enroll"
    And each day should display its actual title from the database
    And the hardcoded preview titles ("Introduction & Setup", "Core Concepts") should NOT appear

  Scenario: CE5 — Admin sees all curriculum even without enrollment
    Given I am logged in as admin
    And I am NOT enrolled in this topic
    When I visit /topics/web-scraping-python
    Then I should see "👑 Admin View" badge
    And I should see the full curriculum from the database
    And I should NOT see "Full curriculum unlocks when you enroll"
    And I should see character count for each day's practice task
