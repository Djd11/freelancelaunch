Feature: Dashboard ↔ Pipeline ↔ Sprint Track Connections
  As a user
  I want all three surfaces to cross-link correctly
  So that I never hit a dead end and the funnel flows Dashboard → Sprint Track → Pipeline

  Background:
    Given the app is running with an in-memory test database
    And a logged-in user with an active cohort
    And a freelance pipeline row exists for the user

  # ═══════════════════════════════════════════════════════════════════
  # DASHBOARD — entry points to Sprint Track and Pipeline
  # ═══════════════════════════════════════════════════════════════════

  Scenario: Dashboard has Sprint Track hero CTA
    When I GET "/dashboard/"
    Then the response status is 200
    And the page contains a link to the sprint track landing page

  Scenario: Dashboard has Sprint Track quick-link
    When I GET "/dashboard/"
    Then the response status is 200
    And the page contains a link to the sprint track landing page

  Scenario: Dashboard has Pipeline quick-link
    When I GET "/dashboard/"
    Then the response status is 200
    And the page contains a link to the freelance pipeline

  Scenario: Dashboard nav bar has Sprint Track
    When I GET "/dashboard/"
    Then the response status is 200
    And the page contains a link to the sprint track landing page

  Scenario: Dashboard nav bar has Pipeline
    When I GET "/dashboard/"
    Then the response status is 200
    And the page contains a link to the freelance pipeline

  # ═══════════════════════════════════════════════════════════════════
  # SPRINT LANDING — back to dashboard
  # ═══════════════════════════════════════════════════════════════════

  Scenario: Sprint landing has nav bar with Dashboard link
    When I GET "/sprints"
    Then the response status is 200
    And the page contains a link to the dashboard

  Scenario: Sprint landing has nav bar with Pipeline link
    When I GET "/sprints"
    Then the response status is 200
    And the page contains a link to the freelance pipeline

  # ═══════════════════════════════════════════════════════════════════
  # SPRINT DASHBOARD — back to main dashboard, links to pipeline
  # ═══════════════════════════════════════════════════════════════════

  Scenario: Sprint dashboard has back-link to main dashboard
    Given I have an active sprint "s1" with 14 days
    When I GET "/sprints/s1"
    Then the response status is 200
    And the page contains a link to the dashboard

  Scenario: Sprint dashboard nav bar has Pipeline link
    Given I have an active sprint "s1" with 14 days
    When I GET "/sprints/s1"
    Then the response status is 200
    And the page contains a link to the freelance pipeline

  Scenario: Sprint dashboard nav bar has Dashboard link
    Given I have an active sprint "s1" with 14 days
    When I GET "/sprints/s1"
    Then the response status is 200
    And the page contains a link to the dashboard

  # ═══════════════════════════════════════════════════════════════════
  # SPRINT DAY — back to sprint dashboard, phase CTAs
  # ═══════════════════════════════════════════════════════════════════

  Scenario: Sprint day has back-link to sprint dashboard
    Given I have an active sprint "s1" with 14 days
    When I GET "/sprints/s1/day/1"
    Then the response status is 200
    And the page contains a link to "/sprints/s1"

  Scenario: Sprint day in Phase B has contract CTA
    Given I have an active sprint "s1" with 14 days
    When I GET "/sprints/s1/day/6"
    Then the response status is 200
    And the page contains a link to "/sprints/s1/contract"

  Scenario: Sprint day in Phase C has proposals CTA
    Given I have an active sprint "s1" with 14 days
    When I GET "/sprints/s1/day/11"
    Then the response status is 200
    And the page contains a link to "/sprints/s1/proposals"

  # ═══════════════════════════════════════════════════════════════════
  # SPRINT CONTRACT — back to sprint dashboard
  # ═══════════════════════════════════════════════════════════════════

  Scenario: Sprint contract has back-link to sprint dashboard
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I GET "/sprints/s1/contract"
    Then the response status is 200
    And the page contains a link to "/sprints/s1"

  Scenario: Sprint contract nav bar has Pipeline link
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I GET "/sprints/s1/contract"
    Then the response status is 200
    And the page contains a link to the freelance pipeline

  # ═══════════════════════════════════════════════════════════════════
  # SPRINT PROPOSALS — back to sprint dashboard, pipeline increment
  # ═══════════════════════════════════════════════════════════════════

  Scenario: Sprint proposals has back-link to sprint dashboard
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I GET "/sprints/s1/proposals"
    Then the response status is 200
    And the page contains a link to "/sprints/s1"

  Scenario: Sprint proposals nav bar has Pipeline link
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    When I GET "/sprints/s1/proposals"
    Then the response status is 200
    And the page contains a link to the freelance pipeline

  Scenario: Submitting a proposal from sprint increments freelance pipeline
    Given I have an active sprint "s1" with 14 days
    And a job cluster "email-automation" with 5 active postings
    And a draft proposal "p1" exists for job "email-automation-1" on sprint "s1"
    When I submit the proposal form to "/sprints/s1/proposals/p1/submit"
    Then the response status is 302
    And the freelance pipeline proposals_sent increments

  # ═══════════════════════════════════════════════════════════════════
  # SPRINT BADGE — back to main dashboard
  # ═══════════════════════════════════════════════════════════════════

  Scenario: Sprint badge has back-link to main dashboard
    Given I have an active sprint "s1" with 14 days
    When I GET "/sprints/s1/badge"
    Then the response status is 200
    And the page contains a link to the dashboard

  Scenario: Sprint badge nav bar has Pipeline link
    Given I have an active sprint "s1" with 14 days
    When I GET "/sprints/s1/badge"
    Then the response status is 200
    And the page contains a link to the freelance pipeline

  # ═══════════════════════════════════════════════════════════════════
  # PIPELINE — back to dashboard (currently missing, should be added)
  # ═══════════════════════════════════════════════════════════════════

  Scenario: Pipeline page has back-link to dashboard
    When I GET "/freelance/pipeline"
    Then the response status is 200
    And the page contains a link to the dashboard

  Scenario: Pipeline page nav bar has Dashboard link
    When I GET "/freelance/pipeline"
    Then the response status is 200
    And the page contains a link to the dashboard

  Scenario: Pipeline page nav bar has Sprint Track link
    When I GET "/freelance/pipeline"
    Then the response status is 200
    And the page contains a link to the sprint track landing page

  # ═══════════════════════════════════════════════════════════════════
  # CROSS-PRODUCT CTA GRAPH — every internal link resolves
  # ═══════════════════════════════════════════════════════════════════

  Scenario: All dashboard CTAs resolve
    When I GET "/dashboard/"
    Then every rendered href resolves to a live page

  Scenario: All sprint landing CTAs resolve
    When I GET "/sprints"
    Then every rendered href resolves to a live page

  Scenario: All sprint dashboard CTAs resolve
    Given I have an active sprint "s1" with 14 days
    When I GET "/sprints/s1"
    Then every rendered href resolves to a live page

  Scenario: All pipeline CTAs resolve
    When I GET "/freelance/pipeline"
    Then every rendered href resolves to a live page

  # ═══════════════════════════════════════════════════════════════════
  # PIPELINE API — /freelance/api/update contract
  # ═══════════════════════════════════════════════════════════════════

  Scenario: Pipeline API accepts stage update
    Given a freelance pipeline row exists for the user
    When I POST to "/freelance/api/update" with JSON {"field": "stage", "value": "applying"}
    Then the response status is 200
    And the JSON response has field "success" equal to true

  Scenario: Pipeline API accepts proposals_sent increment
    Given a freelance pipeline row exists for the user
    When I POST to "/freelance/api/update" with JSON {"field": "proposals_sent", "value": 5}
    Then the response status is 200
    And the JSON response has field "success" equal to true

  Scenario: Pipeline API rejects invalid field
    Given a freelance pipeline row exists for the user
    When I POST to "/freelance/api/update" with JSON {"field": "invalid_field", "value": "x"}
    Then the response status is 400
    And the JSON has error "Invalid field: invalid_field"

  Scenario: Pipeline API is gated for anonymous users
    Given I am not logged in
    When I POST to "/freelance/api/update" with JSON {"field": "stage", "value": "applying"}
    Then the response status is 401
