Feature: Mock Contract & Verification Gate (mockup screen 5)
  As a sprinter in Phase B
  I want to fulfill a real anonymized brief under deadline and constraints, then pass verification to unlock Phase C
  So that I prove I can fulfill, not just learn

  Background:
    Given the app is running against the live test database
    And a logged-in user
    Given I have an active sprint "s1" with 14 days for cluster "email-automation"
    And a job cluster "email-automation" with 5 active postings

  Scenario: The contract page renders an anonymized client brief with deadline and budget
    When I GET "/sprints/s1/contract"
    Then the response status is 200
    And the page contains the text "Client Brief"
    And the page contains the text "Due in"
    And the page contains the text "180"

  Scenario: The brief is derived from a real job post, anonymized
    Given a capstone brief for sprint "s1" references job "email-automation-1"
    When I GET "/sprints/s1/contract"
    Then the page contains the text "Anonymized"
    And the page does not contain any client name

  Scenario: Contract submission requires a deliverable URL
    When I submit the contract form to "/sprints/s1/contract/submit" with no data
    Then the response status is 302
    And the flash message mentions "Paste a link"

  Scenario: Submitting a deliverable records a verification review for gate B
    When I submit the contract form to "/sprints/s1/contract/submit" with submission_url "https://dropbox.com/x"
    Then the response status is 302
    And a verification review for gate "B" is recorded for sprint "s1"

  Scenario: Phase C stays locked until the mock contract passes verification
    Given Phase B has not passed verification for sprint "s1"
    When I GET "/sprints/s1/proposals"
    Then the page contains the text "locked"
    And the page does not contain the text "First-Bid"

  Scenario: Phase C unlocks after verification passes
    Given Phase B has passed verification for sprint "s1"
    When I GET "/sprints/s1/proposals"
    Then the page contains the text "First-Bid"

  Scenario: The badge is not issued until verification passes
    Given Phase B has not passed verification for sprint "s1"
    When I GET "/sprints/s1/badge"
    Then no badge is issued for sprint "s1"

  Scenario: The badge is issued after verification passes and the sprint completes
    Given Phase B has passed verification for sprint "s1"
    And sprint "s1" is completed
    When I GET "/sprints/s1/badge"
    Then a badge is issued for sprint "s1"
