Feature: Demand-Validated Badge
  As a client-ready freelancer
  I want a badge with a live job counter
  So that the immediate ROI of my skill is visible to clients and me

  Scenario: A badge is issued only after a verified sprint
    Given a sprint where the mock contract passed verification
    When the sprint completes
    Then a badge is issued for the cluster
    And the badge records the jobs_at_issue counter at that moment

  Scenario: No badge for merely finishing the course
    Given a sprint that completed without passing mock contract verification
    When the sprint completes
    Then no badge is issued

  Scenario: The badge shows a live job counter
    Given I hold a badge for email-automation
    When I view my profile
    Then the badge shows "N active jobs right now" from job_clusters.job_count
    And a client can filter by "completed this sprint within 30 days"
