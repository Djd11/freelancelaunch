Feature: Curriculum Links Common to All Topics
  As a user viewing any topic detail page
  I want clickable day links whenever curriculum exists in the database
  So that the experience is identical for every topic (web-scraping, n8n, etc.)

  Background:
    Given I am logged in
    And curriculum data exists in the database for a topic

  Scenario: CL1 — Curriculum shows even when not enrolled (cohort-only user)
    Given I am assigned to a cohort for "n8n" but have no pipeline record
    When I visit /topics/n8n-automation
    Then I should see "Full Curriculum" heading with day count
    And each day should be a clickable link to /dashboard/day/<n>
    And I should NOT see the hardcoded "What you'll learn" preview

  Scenario: CL2 — Enrolled user sees curriculum with links
    Given I am enrolled in "web-scraping-python"
    When I visit /topics/web-scraping-python
    Then I should see "Full Curriculum (28 days)"
    And all day rows should link to /dashboard/day/<n>
    And day titles should come from the database (not "Introduction & Setup" fallback)

  Scenario: CL3 — Topic without curriculum shows generate state
    Given no curriculum exists for "seo-content-writing"
    When I visit /topics/seo-content-writing
    Then I should see the "What you'll learn" preview
    And I should see a "Generate My 30-Day Curriculum" button (if enrolled)
    And no day should link to /dashboard/day/<n> yet

  Scenario: CL4 — Curriculum API returns days for any topic
    When I request /search/curriculum/web-scraping-python
    Then it should return all curriculum_days for that topic
    And count should match the number of days in the database
    And each day should have title, day_number, practice_task

  Scenario: CL5 — Cohort videos link to curriculum days
    Given a cohort exists for a topic with curriculum
    When I query cohort_videos for that cohort
    Then each video should have day_number matching curriculum days
    And each video should link to its curriculum_day_id
    And production_status should be "ready"

  Scenario: CL6 — Day page shows content for cohort-only users
    Given I am assigned to an n8n cohort (no pipeline)
    When I visit /dashboard/day/1
    Then the page should load without 500
    And show the day's lesson content from the database
    And show the "Play Video Preview" button

  Scenario: CL7 — Server-rendered links (no JS dependency)
    When I view the topic detail page HTML source
    Then the day links should be present in the server-rendered HTML
    And NOT require JavaScript execution to appear
