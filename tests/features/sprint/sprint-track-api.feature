Feature: V2 Sprint Track API
  As a client of the Sprint Track
  I want the /sprints/* HTTP surface to follow a stable, secure contract
  So that every state change is gated, validated, and returns a correct result

  Background:
    Given the app is running with an in-memory test database
    And a test user is logged in

  # ═══════════════════════════════════════════════════════════════════
  # AUTH GATING — no V2 endpoint is reachable anonymously
  # ═══════════════════════════════════════════════════════════════════

  Scenario: The sprint landing redirects anonymous users to login
    Given I am not logged in
    When I GET "/sprints"
    Then the response status is 302
    And the response redirects to "/auth/login"

  Scenario: Starting a sprint is gated for anonymous users
    Given I am not logged in
    When I submit the start-sprint form to "/sprints/new" for topic "email-automation"
    Then the response status is 302
    And the response redirects to "/auth/login"

  Scenario: Sprint state changes are gated for anonymous users
    Given I am not logged in
    When I POST to "/sprints/s1/day/1/complete"
    Then the response status is 401
    And the JSON has error "not logged in"

  Scenario: Contract submission is gated for anonymous users
    Given I am not logged in
    When I submit the contract form to "/sprints/s1/contract/submit" with submission_url "https://x"
    Then the response status is 302
    And the response redirects to "/auth/login"

  Scenario: Proposal submission is gated for anonymous users
    Given I am not logged in
    When I POST to "/sprints/s1/proposals/p1/submit"
    Then the response status is 302
    And the response redirects to "/auth/login"

  Scenario: Day view is gated for anonymous users
    Given I am not logged in
    When I GET "/sprints/s1/day/1"
    Then the response status is 302
    And the response redirects to "/auth/login"

  Scenario: Contract page is gated for anonymous users
    Given I am not logged in
    When I GET "/sprints/s1/contract"
    Then the response status is 302
    And the response redirects to "/auth/login"

  Scenario: Proposals page is gated for anonymous users
    Given I am not logged in
    When I GET "/sprints/s1/proposals"
    Then the response status is 302
    And the response redirects to "/auth/login"

  Scenario: Badge page is gated for anonymous users
    Given I am not logged in
    When I GET "/sprints/s1/badge"
    Then the response status is 302
    And the response redirects to "/auth/login"

  # ═══════════════════════════════════════════════════════════════════
  # SPRINT CREATION — POST /sprints/new
  # ═══════════════════════════════════════════════════════════════════

  Scenario: A new sprint seeds a job feed and redirects to its dashboard
    When I submit the start-sprint form to "/sprints/new" for topic "email-automation"
    Then the response status is 302
    And the response redirects to "/sprints/{id}"
    And a job cluster "email-automation" exists
    And the sprint has 14 planned days

  Scenario: A new sprint is owned by the creating user
    When I submit the start-sprint form to "/sprints/new" for topic "email-automation"
    Then a sprint row exists for the logged-in user

  Scenario: A new sprint starts in Phase A on day 1
    When I submit the start-sprint form to "/sprints/new" for topic "email-automation"
    Then the created sprint is in phase "A"
    And the created sprint is on day 1

  Scenario: A new sprint seeds an unlock meter snapshot
    When I submit the start-sprint form to "/sprints/new" for topic "email-automation"
    Then an unlock snapshot exists for the created sprint

  Scenario: Starting a sprint for a second cluster also works
    When I submit the start-sprint form to "/sprints/new" for topic "web-scraping"
    Then the response status is 302
    And the response redirects to "/sprints/{id}"
    And a job cluster "web-scraping" exists
    And the sprint has 14 planned days

  # ═══════════════════════════════════════════════════════════════════
  # OWNERSHIP / 404 — a sprint that is not yours is never served
  # ═══════════════════════════════════════════════════════════════════

  Scenario: A sprint that is not yours is not served
    Given an active sprint "other-sprint" on day 1 for another user
    When I GET "/sprints/other-sprint"
    Then the response redirects to "/dashboard/"

  Scenario: A missing sprint redirects to the dashboard
    When I GET "/sprints/does-not-exist"
    Then the response redirects to "/dashboard/"

  Scenario: A day of a missing sprint redirects to the dashboard
    When I GET "/sprints/does-not-exist/day/1"
    Then the response redirects to "/dashboard/"

  # ═══════════════════════════════════════════════════════════════════
  # SPRINT DASHBOARD — GET /sprints/<id>
  # ═══════════════════════════════════════════════════════════════════

  Scenario: The sprint dashboard renders the day track and meter
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 450 active postings
    When I GET "/sprints/s1"
    Then the response status is 200
    And the page contains the text "Job Unlock Meter"

  Scenario: The sprint dashboard exposes all 14 day CTAs
    Given I have an active sprint "s1" with 14 days
    When I GET "/sprints/s1"
    Then the response status is 200
    And the page contains a link to "/sprints/s1/day/1"
    And the page contains a link to "/sprints/s1/day/7"
    And the page contains a link to "/sprints/s1/day/14"

  Scenario: The sprint dashboard exposes proposals, contract and badge CTAs
    Given I have an active sprint "s1" with 14 days
    When I GET "/sprints/s1"
    Then the response status is 200
    And the page contains a link to "/sprints/s1/proposals"
    And the page contains a link to "/sprints/s1/contract"
    And the page contains a link to "/sprints/s1/badge"

  # ═══════════════════════════════════════════════════════════════════
  # DAY VIEW + COMPLETION — GET /sprints/<id>/day/<n>
  #                       POST /sprints/<id>/day/<n>/complete
  # ═══════════════════════════════════════════════════════════════════

  Scenario: Every day view returns 200 for a seeded sprint
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I GET "/sprints/s1/day/1"
    Then the response status is 200
    When I GET "/sprints/s1/day/6"
    Then the response status is 200
    When I GET "/sprints/s1/day/11"
    Then the response status is 200
    When I GET "/sprints/s1/day/14"
    Then the response status is 200

  Scenario: Completing a day advances the sprint and returns the meter
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 450 active postings
    When I POST to "/sprints/s1/day/1/complete"
    Then the response status is 200
    And the JSON has field "ok" equal to true
    And the JSON has field "next_day" equal to 2
    And the JSON path "meter.unlocked" is an integer
    And the sprint "s1" is now on day 2

  Scenario: Completing a day marks the day row done
    Given I have an active sprint "s1" with 14 days
    When I POST to "/sprints/s1/day/3/complete"
    Then day 3 of sprint "s1" is marked done

  Scenario: Completing day 5 advances the sprint into Phase B
    Given I have an active sprint "s1" with 14 days
    When I POST to "/sprints/s1/day/5/complete"
    Then the response status is 200
    And the JSON has field "next_day" equal to 6
    And the sprint "s1" is now on day 6
    And the sprint "s1" is in phase "B"

  Scenario: Completing day 10 advances the sprint into Phase C
    Given I have an active sprint "s1" with 14 days
    When I POST to "/sprints/s1/day/10/complete"
    Then the response status is 200
    And the JSON has field "next_day" equal to 11
    And the sprint "s1" is now on day 11
    And the sprint "s1" is in phase "C"

  Scenario: Completing successive days keeps the meter non-decreasing
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 50 active postings
    When I POST to "/sprints/s1/day/1/complete"
    Then the response status is 200
    And the JSON path "meter.unlocked" is an integer
    When I POST to "/sprints/s1/day/2/complete"
    Then the response status is 200
    And the JSON path "meter.unlocked" is an integer
    And the sprint "s1" is now on day 3

  # ═══════════════════════════════════════════════════════════════════
  # CONTRACT (Phase B) — GET/POST /sprints/<id>/contract[/submit]
  # ═══════════════════════════════════════════════════════════════════

  Scenario: Contract submission requires a submission URL
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I submit the contract form to "/sprints/s1/contract/submit" with no data
    Then the response status is 302
    And the flash message mentions "Paste a link"

  Scenario: A contract can be submitted with a deliverable link
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 450 active postings
    When I submit the contract form to "/sprints/s1/contract/submit" with submission_url "https://dropbox.com/x"
    Then the response status is 302
    And a verification review is recorded for sprint "s1"

  Scenario: The contract page creates a capstone brief from the job feed
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I GET "/sprints/s1/contract"
    Then the response status is 200
    And a capstone brief exists for sprint "s1"

  Scenario: Contract submit redirects back to the contract page
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I submit the contract form to "/sprints/s1/contract/submit" with submission_url "https://github.com/x/pr"
    Then the response status is 302
    And the response redirects to "/sprints/s1/contract"

  # ═══════════════════════════════════════════════════════════════════
  # PROPOSALS (Phase C) — GET /sprints/<id>/proposals
  #                       POST /sprints/<id>/proposals/<pid>/submit
  # ═══════════════════════════════════════════════════════════════════

  Scenario: The proposals page renders live jobs as draft proposals
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    And the user has a verified platform "upwork"
    When I GET "/sprints/s1/proposals"
    Then the response status is 200
    And the page contains the text "First-Bid"

  Scenario: The proposals page seeds draft proposals for live jobs
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    And the user has a verified platform "upwork"
    When I GET "/sprints/s1/proposals"
    Then the response status is 200
    And draft proposals exist for sprint "s1"

  Scenario: Submitting a proposal increments the pipeline count
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    And the user has a verified platform "upwork"
    And a draft proposal "p1" exists for job "email-automation-1" on sprint "s1"
    When I POST to "/sprints/s1/proposals/p1/submit"
    Then the response status is 302
    And the proposal "p1" is marked submitted

  Scenario: Proposal submit redirects back to the proposals page
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    And the user has a verified platform "upwork"
    And a draft proposal "p1" exists for job "email-automation-1" on sprint "s1"
    When I POST to "/sprints/s1/proposals/p1/submit"
    Then the response status is 302
    And the response redirects to "/sprints/s1/proposals"

  # ═══════════════════════════════════════════════════════════════════
  # BADGE — GET /sprints/<id>/badge
  # ═══════════════════════════════════════════════════════════════════

  Scenario: The badge page issues a badge only after verification
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I GET "/sprints/s1/badge"
    Then the response status is 200
    And no badge is issued for sprint "s1"

  Scenario: The badge page issues a badge after a verified mock contract
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    And the mock contract for sprint "s1" has passed verification
    When I GET "/sprints/s1/badge"
    Then the response status is 200
    And a badge is issued for sprint "s1"

  Scenario: The badge page always returns 200 even without verification
    Given I have an active sprint "s1" with 14 days
    When I GET "/sprints/s1/badge"
    Then the response status is 200
