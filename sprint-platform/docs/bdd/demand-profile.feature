Feature: Demand Profile & Client Loop (mockup screen 7)
  As a freelancer (and as a client)
  I want a public profile with live demand-validated badges, case-study portfolio, and a client-side filter
  So that verified supply is fresh, credible, and findable

  Background:
    Given the app is running with an in-memory test database
    And a logged-in user with display name "Maya Chen"

  Scenario: The public profile renders the freelancer's headline and badges
    Given a badge for user "Maya Chen" on cluster "email-automation" with jobs_at_issue 410
    When I GET "/profile/maya"
    Then the response status is 200
    And the page contains the text "Maya Chen"
    And the page contains the text "Demand-Validated"

  Scenario: A badge shows the live counter and trend from snapshots
    Given a badge for user "Maya Chen" on cluster "email-automation" with jobs_at_issue 410
    And job cluster "email-automation" has current job_count 450
    And demand snapshots for "email-automation" show 410 two weeks ago
    When I GET "/profile/maya"
    Then the page contains the text "450 active jobs right now"
    And the page contains the text "410"

  Scenario: A badge shows verification provenance and outcome summary
    Given a badge for user "Maya Chen" on cluster "email-automation"
    And the completed sprint has proposals_sent 5 and interviews_held 1
    When I GET "/profile/maya"
    Then the page contains the text "Mock contract verified"
    And the page contains the text "5 proposals sent"
    And the page contains the text "1 interview"

  Scenario: The portfolio shows case studies in client format
    Given the user has a case study "Abandoned-Cart Recovery Flow"
    When I GET "/profile/maya"
    Then the page contains the text "Abandoned-Cart Recovery Flow"
    And the page contains the text "Problem / Solution / Result"

  Scenario: Clients can filter freelancers by completed sprint within 30 days
    Given freelancer "Maya Chen" has a badge on "email-automation" issued 12 days ago
    And freelancer "Jordan Lee" has a badge on "email-automation" issued 45 days ago
    When I GET "/clients/freelancers?cluster=email-automation&within_days=30"
    Then the response status is 200
    And the page contains the text "Maya Chen"
    And the page does not contain the text "Jordan Lee"

  Scenario: A private profile is not listed in the client filter
    Given freelancer "Maya Chen" has profile is_public equal to false
    When I GET "/clients/freelancers?cluster=email-automation&within_days=30"
    Then the page does not contain the text "Maya Chen"

  Scenario: No badge is shown without verification
    Given the user has no passing verification for any sprint
    When I GET "/profile/maya"
    Then the page does not contain any badge
