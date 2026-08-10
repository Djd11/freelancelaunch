Feature: V2 Sprint Track Navigation
  As a logged-in sprinter
  I want every CTA to render a working link that lands me on the right page
  So that the Sprint Track is reachable and no dead-end / orphaned UI exists

  Background:
    Given the app is running with an in-memory test database
    And a logged-in user with an active cohort

  # ═══════════════════════════════════════════════════════════════════
  # ENTRY POINTS — the gap that previously let V2 fall off the map
  # ═══════════════════════════════════════════════════════════════════

  Scenario: The nav bar renders a Sprint Track link to the sprint landing
    When I open the authenticated dashboard
    Then the page contains a link to "/sprints"
    And the link has text "Sprint Track"
    When I click through to "/sprints"
    Then the response status is 200
    And the page is the Sprint Track landing

  Scenario: The dashboard hero card links to the Sprint Track landing
    When I open the authenticated dashboard
    Then the page contains a link to "/sprints"
    And the page contains the text "Open Sprint Track"
    And the page contains the text "Sprint Track"
    And the page contains the text "14-day placement"

  Scenario: The dashboard quick-link row links to the Sprint Track
    When I open the authenticated dashboard
    Then the page contains a link to "/sprints"
    And the page contains the text "Sprint Track"

  Scenario: Every authenticated entry point lands on the same Sprint Track landing
    When I open the authenticated dashboard
    And I click through to "/sprints"
    Then the response status is 200
    And the page is the Sprint Track landing
    And the page contains a form posting to "/sprints/new"

  # ═══════════════════════════════════════════════════════════════════
  # LANDING — start-sprint CTA + resume existing sprint
  # ═══════════════════════════════════════════════════════════════════

  Scenario: The start-sprint CTA posts to the sprint creation endpoint
    Given I am on the Sprint Track landing
    Then the page contains a form posting to "/sprints/new"
    And the form has a select named "topic"
    And the page contains the text "Start Sprint"

  Scenario: The start-sprint CTA creates a sprint and lands on its dashboard
    When I start a sprint for cluster "email-automation"
    Then the response redirects to "/sprints/{id}"
    When I follow the redirect
    Then the response status is 200
    And the page is the sprint dashboard for "email-automation"

  Scenario: Landing lists an existing sprint with a resume CTA to its dashboard
    Given I have an active sprint "s1" with 14 days
    Given I am on the Sprint Track landing
    Then the page contains a link to "/sprints/s1"
    When I click through to "/sprints/s1"
    Then the response status is 200
    And the page is the sprint dashboard for "email-automation"

  # ═══════════════════════════════════════════════════════════════════
  # SPRINT DASHBOARD — every outbound CTA
  # ═══════════════════════════════════════════════════════════════════

  Scenario: The sprint dashboard links to each day's view
    Given I have an active sprint "s1" with 14 days
    When I open the sprint dashboard for "s1"
    Then the page contains a link to "/sprints/s1/day/1"
    And the page contains a link to "/sprints/s1/day/14"
    And each sprint-day CTA resolves to a 200 page

  Scenario: The sprint dashboard "Open Day" CTA targets the current day
    Given I have an active sprint "s1" with 14 days
    When I open the sprint dashboard for "s1"
    Then the page contains a link to "/sprints/s1/day/1"
    And the page contains the text "Open Day"

  Scenario: The sprint dashboard links to proposals
    Given I have an active sprint "s1" with 14 days
    When I open the sprint dashboard for "s1"
    Then the page contains a link to "/sprints/s1/proposals"
    When I click through to "/sprints/s1/proposals"
    Then the response status is 200
    And the page is the proposals page

  Scenario: The sprint dashboard links to the mock contract
    Given I have an active sprint "s1" with 14 days
    When I open the sprint dashboard for "s1"
    Then the page contains a link to "/sprints/s1/contract"
    When I click through to "/sprints/s1/contract"
    Then the response status is 200
    And the page is the contract page

  Scenario: The sprint dashboard links to the badge page
    Given I have an active sprint "s1" with 14 days
    When I open the sprint dashboard for "s1"
    Then the page contains a link to "/sprints/s1/badge"
    When I click through to "/sprints/s1/badge"
    Then the response status is 200
    And the page is the badge page

  Scenario: The sprint dashboard links back to the v1 dashboard
    Given I have an active sprint "s1" with 14 days
    When I open the sprint dashboard for "s1"
    Then the page contains a link to "/dashboard/"

  Scenario: The sprint dashboard renders the Job Unlock Meter
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I open the sprint dashboard for "s1"
    Then the response status is 200
    And the page contains the text "Job Unlock Meter"

  # ═══════════════════════════════════════════════════════════════════
  # DAY VIEW — phase-aware CTAs + complete-day
  # ═══════════════════════════════════════════════════════════════════

  Scenario: A Phase A day view links back to the sprint dashboard
    Given I have an active sprint "s1" with 14 days
    When I open "/sprints/s1/day/2"
    Then the response status is 200
    And the page contains a link to "/sprints/s1"

  Scenario: A Phase B day view links to the mock contract brief
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I open "/sprints/s1/day/6"
    Then the response status is 200
    And the page contains a link to "/sprints/s1/contract"

  Scenario: A Phase C day view links to the proposal builder
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I open "/sprints/s1/day/11"
    Then the response status is 200
    And the page contains a link to "/sprints/s1/proposals"

  Scenario: The day view offers a complete-day action that returns the meter
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I complete day 1 of sprint "s1"
    Then the response status is 200
    And the JSON has field "ok" equal to true
    And the JSON has field "next_day" equal to 2
    And the JSON path "meter.unlocked" is an integer

  # ═══════════════════════════════════════════════════════════════════
  # CONTRACT / PROPOSALS / BADGE — back-links and form CTAs
  # ═══════════════════════════════════════════════════════════════════

  Scenario: The contract page is reachable and links back to the sprint dashboard
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I open "/sprints/s1/contract"
    Then the response status is 200
    And the page is the contract page
    And the page contains a link to "/sprints/s1"
    And the page contains a form posting to "/sprints/s1/contract/submit"

  Scenario: The proposals page is reachable and links back to the sprint dashboard
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I open "/sprints/s1/proposals"
    Then the response status is 200
    And the page is the proposals page
    And the page contains a link to "/sprints/s1"

  Scenario: The badge page is reachable and links back to the v1 dashboard
    Given I have an active sprint "s1" with 14 days
    When I open "/sprints/s1/badge"
    Then the response status is 200
    And the page is the badge page
    And the page contains a link to "/dashboard/"

  # ═══════════════════════════════════════════════════════════════════
  # FULL CTA GRAPH — every rendered href on every V2 page is live
  # ═══════════════════════════════════════════════════════════════════

  Scenario: Every CTA on the Sprint Track landing resolves to a live page
    Given I have an active sprint "s1" with 14 days
    Given I am on the Sprint Track landing
    Then every rendered href resolves to a live page

  Scenario: Every CTA on the sprint dashboard resolves to a live page
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I open the sprint dashboard for "s1"
    Then every rendered href resolves to a live page

  Scenario: Every CTA on a day view resolves to a live page
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I open "/sprints/s1/day/1"
    Then every rendered href resolves to a live page

  Scenario: Every CTA on the contract page resolves to a live page
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I open "/sprints/s1/contract"
    Then every rendered href resolves to a live page

  Scenario: Every CTA on the proposals page resolves to a live page
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I open "/sprints/s1/proposals"
    Then every rendered href resolves to a live page

  Scenario: Every CTA on the badge page resolves to a live page
    Given I have an active sprint "s1" with 14 days
    When I open "/sprints/s1/badge"
    Then every rendered href resolves to a live page

  # ═══════════════════════════════════════════════════════════════════
  # AUTH GATING — no V2 CTA is reachable anonymously
  # ═══════════════════════════════════════════════════════════════════

  Scenario: Every sprint GET CTA redirects anonymous users to login
    Given I am not logged in
    When I open "/sprints"
    Then the response redirects to "/auth/login"
    When I open "/sprints/s1"
    Then the response redirects to "/auth/login"
    When I open "/sprints/s1/day/1"
    Then the response redirects to "/auth/login"
    When I open "/sprints/s1/contract"
    Then the response redirects to "/auth/login"
    When I open "/sprints/s1/proposals"
    Then the response redirects to "/auth/login"
    When I open "/sprints/s1/badge"
    Then the response redirects to "/auth/login"
