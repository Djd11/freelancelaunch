Feature: Sprint Dashboard (mockup screen 3)
  As a sprinter
  I want a dashboard that shows the phase-locked track, the Job Unlock Meter, today's task, and momentum
  So that I always know where I am and what to do next

  Background:
    Given the app is running against the live test database
    And a logged-in user
    Given I have an active sprint "s1" with 14 days for cluster "email-automation"

  Scenario: Dashboard shows the sprint header with day, phase, and cohort
    When I GET "/sprints/s1"
    Then the response status is 200
    And the page contains the text "Email Automation Sprint"
    And the page contains the text "Day 4"
    And the page contains the text "Phase A"

  Scenario: Dashboard renders the three phase cards with locks
    When I GET "/sprints/s1"
    Then the page contains the text "Skill Acquisition"
    And the page contains the text "Mock Contract"
    And the page contains the text "Send Proposals"

  Scenario: Phase B is locked until Phase A passes verification
    Given Phase A has not passed verification for sprint "s1"
    When I GET "/sprints/s1"
    Then the page contains a lock indicator on Phase B
    And the page contains the text "Unlocks when Phase A passes verification"

  Scenario: Phase C is locked until the Mock Contract passes verification
    Given Phase B has not passed verification for sprint "s1"
    When I GET "/sprints/s1"
    Then the page contains a lock indicator on Phase C

  Scenario: Phase B unlocks after Phase A passes verification
    Given Phase A has passed verification for sprint "s1"
    When I GET "/sprints/s1"
    Then Phase B is not locked

  Scenario: The Job Unlock Meter shows unlocked / total and a delta chip
    Given the meter for sprint "s1" has unlocked 186 of 450 with delta 38
    When I GET "/sprints/s1"
    Then the page contains the text "Job Unlock Meter"
    And the page contains the text "186"
    And the page contains the text "450"
    And the page contains the text "+38"

  Scenario: The today card shows the current day's three check items
    Given I am on day 4 of sprint "s1"
    When I GET "/sprints/s1"
    Then the page contains the text "Today"
    And the page contains the text "Watch lesson"
    And the page contains the text "Replicate the project"
    And the page contains the text "Self-check vs rubric"

  Scenario: The momentum card shows streak, confidence, proposals, and contracts
    Given user momentum with streak 4 and confidence 72
    And sprint "s1" has 0 proposals sent and 0 contracts
    When I GET "/sprints/s1"
    Then the page contains the text "Momentum"
    And the page contains the text "4"
    And the page contains the text "72"
    And the page contains the text "Proposals sent"
    And the page contains the text "Contracts"

  Scenario: Completing a day advances to the next day and unlocks job postings
    When I POST to "/sprints/s1/day/4/complete"
    Then the response status is 302
    And the response redirects to a day page
    And the sprint "s1" is now on day 5

  Scenario: A sprint that is not yours is never served
    Given an active sprint "other-sprint" for another user
    When I GET "/sprints/other-sprint"
    Then the response redirects to "/dashboard/"

  Scenario: The dashboard shows the cohort line with its end date
    When I GET "/sprints/s1"
    Then the page contains the text "Cohort #12"
    And the page contains the text "ends 2026-08-23"

  Scenario: A fully generated sprint shows the 14 day-content cards
    Given I am on day 4 of sprint "s1"
    When the content generation worker runs for sprint "s1"
    And I GET "/sprints/s1"
    Then the response status is 200
    And the page contains the text "Sprint Content"
    And the page contains the text "14 / 14 days generated"

  Scenario: Each day card exposes its generated lesson title
    Given I am on day 4 of sprint "s1"
    When the content generation worker runs for sprint "s1"
    And I GET "/sprints/s1"
    Then the page contains the text "Day lesson for"

  Scenario: A day whose generation failed is marked on the dashboard
    Given I am on day 4 of sprint "s1"
    When the content generation worker runs for sprint "s1" with no LLM
    And I GET "/sprints/s1"
    Then the page contains the text "Generation failed"
