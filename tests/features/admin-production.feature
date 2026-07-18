Feature: Admin Production Dashboard (Browser)
  As an admin user
  I want to monitor and trigger video production from the dashboard
  So that I can manage the video pipeline

  Background:
    Given I am logged in as an admin user
    And there are cohort_videos with various production_status values

  Scenario: View production queue
    When I navigate to the admin production page
    Then I should see pending videos in the "Pending" section
    And I should see recent videos in the "Recent" section
    And each video should show its day number and status

  Scenario: Trigger production from dashboard
    Given there is a pending cohort_video
    When I click the "Produce Now" button for that video
    Then the production status should change to "scripting" or "rendering"
    And a success flash message should appear

  Scenario: Status badges show correct colors
    When I view the production page
    Then "ready" status should have a green badge
    And "failed" status should have a red badge
    And "pending" status should have a gray badge
    And "rendering" status should have an indigo badge

  Scenario: Nightly schedule info is visible
    When I view the admin production page
    Then I should see the cron schedule information
    And the cron command should be displayed in a code block
