Feature: Sprint Start (eng-spec J2) — idempotent enrollment
  As a learner
  I want starting a sprint for a cluster to be idempotent
  So that a double-click or a revisit never creates a duplicate sprint or 500s

  Background:
    Given the app is running against the live test database
    And a logged-in user with display name "Maya Chen"
    And a job cluster "email-automation" with job_count 450 and avg_rate 62 and growth_score 18
    And the user has a verified platform "upwork"

  Scenario: Starting a sprint twice is idempotent
    When I start a sprint for cluster "email-automation" from the picker
    Then the response status is 302
    When I start the sprint again from the picker
    Then the response status is 302
    And the response redirects to the same sprint
