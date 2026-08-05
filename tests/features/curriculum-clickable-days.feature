Feature: Curriculum Days are Clickable with Visible Content
  As an enrolled user viewing the curriculum
  I want each day to be a clickable link with detailed content
  So that I can access each day's full lesson

  Background:
    Given I am logged in and enrolled in a topic with 30 curriculum days

  Scenario: CD1 — Each day row is a clickable link
    When I view the curriculum section
    Then each day should be wrapped in a clickable link
    And the link should point to /dashboard/day/<day_number>
    And clicking a day should navigate to that day's detail page

  Scenario: CD2 — Day link shows day number and title
    When I view the curriculum list
    Then each row should display the day number (e.g., "Day 1")
    And each row should display the day title (e.g., "HTTP Requests")
    And each row should display a practice task preview

  Scenario: CD3 — Day detail page shows full lesson
    Given I click on Day 1 in the curriculum
    When the day detail page loads
    Then I should see the day number and title as heading
    And I should see the full lesson content (Hook, Concept, Practice, Retrieval)
    And I should see the practice task
    And I should see a "Back to Topic" link

  Scenario: CD4 — All 30 days are present and numbered
    When I view the curriculum section
    Then I should see exactly 30 day entries
    And the day numbers should be sequential 1 through 30

  Scenario: CD5 — Day content is not generic fallback
    When I view the curriculum
    Then at least 3 different unique practice tasks should exist
    And day titles should be unique (no "Part X" pattern)
    And no day should contain "Hands-on exercise related to today's"
    
  Scenario: CD6 — Day detail page loads correctly for each day
    When I visit /dashboard/day/1
    Then the page should load without errors
    And I should see the day number "Day 1"
    And I should see lesson content

  Scenario: CD7 — Clicking a day from curriculum navigates correctly
    Given I am on the topic detail page
    When I click on the Day 5 link
    Then the URL should be /dashboard/day/5
    And the page should show Day 5 content
