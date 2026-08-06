# Dashboard Course Stats — BDD Specification
# The dashboard must capture and surface three core course statistics at a glance:
#   1. HOW MANY courses the learner is engaged with (course count)
#   2. WHAT the progress is (days completed + progress bar / percentage)
#   3. WHERE the learner currently is in the course (current position: Day N of M)
#
# This feature drives the step module tests/steps/test_dashboard_course_stats.py,
# which "captures" the stats off the rendered page (into context.course_stats) and
# then verifies them — exactly what a real user sees.

Feature: Dashboard Course Stats
  As a learner
  I want the dashboard to capture my course count, my progress, and my current position
  So that I can tell at a glance how many courses I have, how far along I am,
  and exactly where to pick up next

  Background:
    Given the application is running at http://localhost:5000
    And the audit browser is Google Chrome (non-headless, DISPLAY=:0)
    And I am logged in

  Scenario: CS-1 — Dashboard captures HOW MANY courses the learner has
    When I visit /dashboard/
    Then I should see the "YOUR COURSES" heading
    And I capture the course stats from the dashboard
    And the captured course count should be at least 1
    And the captured course count should match the number of course tabs rendered

  Scenario: CS-2 — Dashboard captures WHAT the progress is for every course
    When I visit /dashboard/
    And I capture the course stats from the dashboard
    Then every captured course tab should show a progress fraction "done/total"
    And the captured active course should show a "days completed" label
    And the captured active course progress bar should be a valid percentage between 0% and 100%

  Scenario: CS-3 — Dashboard captures WHERE the learner currently is
    When I visit /dashboard/
    And I capture the course stats from the dashboard
    Then the captured current position should read "Day N of M"
    And the captured current day N should be between 1 and M
    And the captured progress fraction total should match the position total M
