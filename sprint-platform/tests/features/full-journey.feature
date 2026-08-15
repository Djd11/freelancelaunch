Feature: Full Learner Journey (eng-spec J1→J7 chained)
  As a learner
  I want to go from landing page to badge to client-visible profile in one unbroken chain
  So that the platform's core promise — demand-validated placement — is proven end to end

  Background:
    Given the app is running against the live test database
    And a logged-in user with display name "Maya Chen"
    And a job cluster "email-automation" with job_count 450 and avg_rate 62 and growth_score 18
    And the user has a verified platform "upwork"

  Scenario: Landing to badge to client filter — the complete journey
    # J1 — landing renders the promise
    When I GET "/"
    Then the response status is 200
    And the page contains the text "Stop learning skills."

    # J2 — picker offers the cluster, starting a sprint creates it
    When I start a sprint for cluster "email-automation" from the picker
    And I open the journey dashboard
    Then the response status is 200
    And the page contains the text "Email Automation Sprint"
    And the page contains the text "Cohort #12"

    # J3 — Phase A: days 1–5 complete, each returning a meter update
    When I complete day 1 of the journey sprint
    Then the JSON has field "ok" equal to true
    And the JSON path "meter.newly_unlocked" is an integer
    When I complete day 2 of the journey sprint
    Then the JSON has field "ok" equal to true
    When I complete day 3 of the journey sprint
    Then the JSON has field "ok" equal to true
    When I complete day 4 of the journey sprint
    Then the JSON has field "ok" equal to true
    When I complete day 5 of the journey sprint
    Then the JSON has field "ok" equal to true
    And the journey sprint is on day 6

    # J4 — copy-work submitted, gate A passes, Phase B unlocks
    When I submit copy-work for day 4 of the journey sprint with rubric_url "https://github.com/maya/flow"
    Then the response status is 302
    And a verification review for gate "A" is recorded for the journey sprint
    When the verification service passes gate "A" for the journey sprint
    And I open the journey dashboard
    Then Phase B is not locked

    # J5 — Phase B: contract brief rendered, deliverable submitted, gate B passes
    When I open the journey contract
    Then the response status is 200
    And the page contains the text "Client Brief"
    When I submit the journey contract deliverable with submission_url "https://dropbox.com/maya-deliverable"
    Then the response status is 302
    And a verification review for gate "B" is recorded for the journey sprint
    When the verification service passes gate "B" for the journey sprint

    # J6 — Phase C unlocks, first proposal submitted by the human
    When I open the journey proposals page
    Then the response status is 200
    And the page contains the text "First-Bid"
    When I submit the first draft proposal of the journey sprint on platform "upwork"
    Then the journey sprint has proposals_sent equal to 1

    # J7 — completion, badge, public provenance, client filter
    When the journey sprint is marked completed
    And I request the journey badge
    Then a badge is issued for the journey sprint
    When I GET "/profile/maya"
    Then the response status is 200
    And the page contains the text "Demand-Validated"
    And the page contains the text "Mock contract verified"
    When I GET "/clients/freelancers?cluster=email-automation&within_days=30"
    Then the response status is 200
    And the page contains the text "Maya Chen"
