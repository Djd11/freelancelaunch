Feature: Proposal Builder & First-Bid Challenge (mockup screen 6)
  As a sprinter in Phase C
  I want engineered proposals with job-specific hooks and a 5-proposal First-Bid challenge
  So that I convert my verified mock contract into interviews

  Background:
    Given the app is running against the live test database
    And a logged-in user
    Given I have an active sprint "s1" with 14 days for cluster "email-automation"
    And a job cluster "email-automation" with 5 active postings
    And Phase B has passed verification for sprint "s1"

  Scenario: The proposals page renders live jobs as draft proposals
    And the user has a verified platform "upwork"
    When I GET "/sprints/s1/proposals"
    Then the response status is 200
    And the page contains the text "First-Bid"
    And draft proposals exist for sprint "s1"

  Scenario: A proposal template is generated with job-specific hooks and proof from the mock contract
    Given a capstone brief for sprint "s1" exists
    And the user has a verified platform "upwork"
    When the proposal drafts are generated for sprint "s1"
    And I GET "/sprints/s1/proposals"
    Then the page contains the text "I see you need"
    And the page contains the text "Mock Contract"

  Scenario: Proposal proof references the learner's actual submitted deliverable
    Given copy-work project 1 for sprint "s1" has submitted_url "https://me.dev/p1" and rubric_checked all true
    When the proposal drafts are generated for sprint "s1"
    Then the proposal for the live job mentions "https://me.dev/p1"

  Scenario: A proposal whose generation failed surfaces a visible error, never a template
    And the user has a verified platform "upwork"
    When the proposal drafts are generated for sprint "s1" with no LLM
    And I GET "/sprints/s1/proposals"
    Then the page contains the text "Proposal generation failed"

  Scenario: First-Bid challenge tracks progress out of 5
    Given the user has a verified platform "upwork"
    And a draft proposal "p1" exists for job "email-automation-1" on sprint "s1"
    When I submit the proposal form to "/sprints/s1/proposals/p1/submit"
    Then the proposal "p1" is marked submitted
    And sprint "s1" has proposals_sent equal to 1

  Scenario: Submitting a proposal is human-initiated — never auto-submitted
    Given the user has a verified platform "upwork"
    And a draft proposal "p1" exists for job "email-automation-1" on sprint "s1"
    Then the proposal "p1" remains a draft until the user confirms submission

  Scenario: Proposal submission records the marketplace platform
    Given the user has a verified platform "upwork"
    And a draft proposal "p1" exists for job "email-automation-1" on sprint "s1"
    When I choose platform "upwork" and submit the proposal form to "/sprints/s1/proposals/p1/submit"
    Then the proposal "p1" is submitted on platform "upwork"

  Scenario: Submitting on a platform you have not verified is rejected
    Given the user has verified platforms "upwork" and "fiverr"
    And a draft proposal "p1" exists for job "email-automation-1" on sprint "s1"
    When I choose platform "contra" and submit the proposal form to "/sprints/s1/proposals/p1/submit"
    Then the proposal "p1" remains a draft

  Scenario: The iteration loop diagnoses a stall after 5 proposals with no responses
    Given sprint "s1" has proposals_sent equal to 5
    And sprint "s1" has responses_received equal to 0
    When the sprint reaches day 14
    Then the iteration engine returns a diagnosis of price, portfolio, or niche
