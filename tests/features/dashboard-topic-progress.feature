# Dashboard Learning-Stage — BDD Specification
# The dashboard must show the user's current learning stage per topic in
# horizontal tabs — never a meaningless "Day 0" placeholder, and never a
# generic "Ready to start learning?" that hides the real next step.

Feature: Dashboard Topic Progress
  As a learner
  I want the dashboard to show my current learning stage for every course
  So that I always know exactly where to pick up each topic

  Background:
    Given the application is running at http://localhost:5000
    And the audit browser is Google Chrome (non-headless, DISPLAY=:0)
    And I am logged in

  Scenario: DP-1 — Dashboard has a horizontal course-tab strip
    When I visit /dashboard/
    Then I should see "YOUR COURSES"
    And I should see "Web Scraping with Python"

  Scenario: DP-2 — The active course shows a real stage, never "Day 0"
    When I visit /dashboard/
    Then I should see "days completed"
    And I should NOT see "Day 0"

  Scenario: DP-3 — No generic "cohort hasn't started" placeholder
    When I visit /dashboard/
    Then I should NOT see "Ready to start learning?"
    And I should NOT see "Your first video will appear here when your cohort starts."

  Scenario: DP-4 — Not-started course offers "Start Day N" deep link with topic
    When I visit /dashboard/?topic=web-scraping-python
    Then I should see "Start Day 1" link → /dashboard/day/1?topic=web-scraping-python

  Scenario: DP-5 — Topic-scoped dashboard renders the correct active course
    When I visit /dashboard/?topic=web-scraping-python
    Then I should see "Web Scraping with Python"
    And I should see "days completed"
    And I should NOT see "Day 0"
    And the page must have zero console errors and zero failed requests
