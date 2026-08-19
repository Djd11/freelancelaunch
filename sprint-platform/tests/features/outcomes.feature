Feature: Outcome Tracking, Verification Auto-Check & Sprint Completion (eng-spec §4.2, §4.3, §5.6)
  As a sprinter
  I want gates to auto-check, contracts to roll up earnings, and the sprint to complete at Day 14
  So that the platform works end-to-end without an admin babysitting every review

  Background:
    Given the app is running against the live test database
    And a logged-in user
    Given I have an active sprint "s1" with 14 days for cluster "email-automation"
    And a job cluster "email-automation" with 5 active postings
    And the user has a verified platform "upwork"

  Scenario: Gate A auto-passes once all three copy-work projects are done
    Given copy-work projects 1, 2, and 3 for sprint "s1" are done
    When I submit the copy-work task for day 4 of sprint "s1" with rubric_url "https://github.com/me/flow"
    Then the response status is 302
    And gate "A" has passed verification for sprint "s1"

  Scenario: Gate B auto-passes when the deliverable is submitted and Phase C unlocks
    When I save the case study "Abandoned-Cart Recovery Flow" for sprint "s1"
    And I submit the contract form to "/sprints/s1/contract/submit" with submission_url "https://dropbox.com/x"
    Then the response status is 302
    And gate "B" has passed verification for sprint "s1"
    When I GET "/sprints/s1/proposals"
    Then the page contains the text "First-Bid"

  Scenario: Recording a contract rolls up earnings on the sprint record
    When I add a contract of value 300 with 20 hours on platform "upwork" for sprint "s1"
    Then sprint "s1" has contracts_won equal to 1
    And sprint "s1" has total_earned equal to 300
    And sprint "s1" has avg_contract_value equal to 300
    And sprint "s1" has a first_contract_at timestamp

  Scenario: Completing day 14 completes the sprint
    When I POST to "/sprints/s1/day/14/complete"
    Then the response status is 302
    And the response redirects to the sprint dashboard
    And sprint "s1" is completed

  Scenario: The iteration loop surfaces a diagnosis after 5 proposals with no responses
    Given sprint "s1" has proposals_sent equal to 5
    And sprint "s1" has responses_received equal to 0
    And Phase B has passed verification for sprint "s1"
    When I GET "/sprints/s1/proposals"
    Then the page contains the text "portfolio"

  Scenario: Logging a response outcome is tracked on the sprint
    Given a draft proposal "p1" exists for job "email-automation-1" on sprint "s1"
    And Phase B has passed verification for sprint "s1"
    When I log outcome "response" for proposal "p1" on sprint "s1"
    Then sprint "s1" has responses_received equal to 1

  Scenario: A case study is saved against the sprint
    When I save the case study "Abandoned-Cart Recovery Flow" for sprint "s1"
    Then a case study titled "Abandoned-Cart Recovery Flow" exists for sprint "s1"
