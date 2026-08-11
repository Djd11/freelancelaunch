Feature: Landing (mockup screen 1)
  As a prospective learner
  I want a marketing page that shows the demand-validated sprint promise and a live demand counter
  So that I understand the 14-day placement sprint and am motivated to start

  Background:
    Given the app is running with an in-memory test database

  Scenario: Landing renders without auth
    When I GET "/"
    Then the response status is 200
    And the page contains the text "Stop learning skills."
    And the page contains the text "Start landing clients."

  Scenario: Landing shows the three-phase story
    When I GET "/"
    Then the page contains the text "Skill Acquisition"
    And the page contains the text "Mock Contract"
    And the page contains the text "Supply Chain"

  Scenario: Landing renders the live demand counter from the job cluster
    Given a job cluster "email-automation" with job_count 450 and avg_rate 62 and growth_score 18
    When I GET "/"
    Then the page contains the text "450"
    And the page contains the text "median hourly rate"
    And the page contains the text "+18%"

  Scenario: Landing offers a Start CTA and pricing link
    When I GET "/"
    Then the page contains a link to "/sprints"
    And the page contains a link to "/pricing"

  Scenario: Landing CTA band explains the Demand-Validated badge
    When I GET "/"
    Then the page contains the text "Demand-Validated"
    And the page contains the text "live job count"
