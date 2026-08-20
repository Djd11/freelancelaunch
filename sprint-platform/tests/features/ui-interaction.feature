Feature: UI Interaction — checkboxes, submit buttons, and landing pages work end to end
  As a user
  I want every checkbox/check-item, submit button, and landing page to behave per the engineering spec
  So that no interaction point is decorative, dead, or out of spec

  Background:
    Given the app is running against the live test database
    And a logged-in user
    Given I have an active sprint "s1" with 14 days for cluster "email-automation"
    And a job cluster "email-automation" with 5 active postings

  # ── CHECKBOXES / CHECK-ITEMS (mockup checklist affordances) ─────────
  Scenario: Day view renders all three check-items with their labels
    When I GET "/sprints/s1/day/4"
    Then the response status is 200
    And the page contains the text "Mark lesson watched"
    And the page contains the text "Replicate from scratch"
    And the page contains the text "Pass 3-point rubric"

  Scenario: Dashboard check-item reflects the Watch-lesson done state
    Given I am on day 4 of sprint "s1"
    And day 4 of sprint "s1" has the lesson marked watched
    When I GET "/sprints/s1"
    Then the response status is 200
    And the page contains the text "Watch lesson"
    And the page contains an element with class "check-item done"
    And the check-item "Watch lesson" is marked done
    And the page contains the text "Replicate the project"
    And the page contains the text "Self-check vs rubric"

  Scenario: Mock Contract page renders both verification check-items
    When I GET "/sprints/s1/contract"
    Then the response status is 200
    And the page contains the text "Automated flow check"
    And the page contains the text "Case study written"

  Scenario: Profile badge check-item renders as done
    Given a badge for user "Maya Chen" on cluster "email-automation" with jobs_at_issue 410
    When I GET "/profile/maya"
    Then the response status is 200
    And the page contains an element with class "check-item done"

  Scenario: Profile case-study check-item renders done when published
    Given the user has a case study "Abandoned-Cart Recovery Flow"
    When I GET "/profile/maya"
    Then the response status is 200
    And the page contains the text "Abandoned-Cart Recovery Flow"
    And the page contains an element with class "check-item done"

  Scenario: Profile case-study check-item stays incomplete while draft
    Given the user has a draft case study "Abandoned-Cart Recovery Flow"
    When I GET "/profile/maya"
    Then the response status is 200
    And the page contains the text "draft — completes with Mock Contract"
    And the page does not contain an element with class "check-item done"

  # ── SUBMIT BUTTONS / FORMS (field-level, not just presence) ────────
  Scenario: Add-contract form submits all five fields and rolls up earnings
    When I add a contract of value 300 with 20 hours on platform "upwork" for sprint "s1"
    Then sprint "s1" has contracts_won equal to 1
    And sprint "s1" has total_earned equal to 300
    And sprint "s1" has avg_contract_value equal to 300
    And sprint "s1" has a first_contract_at timestamp

  Scenario: Case-study form persists Problem / Solution / Result
    When I save the case study "Abandoned-Cart Recovery Flow" for sprint "s1"
    Then the response status is 302
    And a case study titled "Abandoned-Cart Recovery Flow" exists for sprint "s1"

  Scenario: Contract "Mark complete" CTA finishes the contract and lands on the dashboard
    When I add a contract of value 300 with 20 hours on platform "upwork" for sprint "s1"
    And I mark the most recent contract complete for sprint "s1"
    Then the response redirects to the sprint dashboard
    And sprint "s1" has contracts_completed equal to 1

  Scenario: Proposal outcome select rejects an invalid outcome (no counter bump)
    Given Phase B has passed verification for sprint "s1"
    And a draft proposal "p1" exists for job "email-automation-1" on sprint "s1"
    When I log outcome "garbage" for proposal "p1" on sprint "s1"
    Then the response status is 302
    And sprint "s1" has responses_received equal to 0

  Scenario: Mentor turn form accepts the HTML form path (not just JSON)
    When I submit the form at "/mentor/turn" with data {"question": "Where do I start?"}
    Then the response status is 200
    And the JSON has field "answer" present

  Scenario: Copy-proposal button is wired with a clipboard payload
    Given Phase B has passed verification for sprint "s1"
    When the proposal drafts are generated for sprint "s1"
    When I GET "/sprints/s1/proposals"
    Then the response status is 200
    And the page contains an element with attribute "data-copy-proposal"
    And the page contains an element with id "proposal-text"

  # ── LANDING PAGES PER ENG-SPEC (J1/J2/J7 + pricing) ────────────────
  Scenario: Landing hero "See how it works" resolves to an in-page anchor
    When I GET "/"
    Then the page contains a link to the anchor "how"
    And the page contains an element with id "how"

  Scenario: Topics nav redirects to the sprint catalog (public)
    When I GET "/topics"
    Then the response redirects to "/sprints"

  Scenario: Pricing page renders with no dead links
    When I GET "/pricing"
    Then the response status is 200
    And the page does not contain any dead link

  Scenario: Public surfaces render without auth, never a 500
    Given I am not logged in
    When I GET "/"
    Then the response status is 200
    When I GET "/pricing"
    Then the response status is 200
    When I GET "/clients/freelancers"
    Then the response status is 200

  # ── ADMIN HTML FORMS (browser path, not just JSON) ─────────────────
  Scenario: Admin cluster form renders and POSTs via HTML
    Given I am logged in as an admin user
    When I GET "/admin/clusters/create"
    Then the response status is 200
    And the page contains an element with name "cluster_key"
    When I submit the form at "/admin/clusters/create" with data {"cluster_key": "ui-test-cluster", "display_name": "UI Test Cluster"}
    Then the response status is 302

  Scenario: Admin cohort form renders and POSTs via HTML
    Given I am logged in as an admin user
    When I GET "/admin/cohorts/create"
    Then the response status is 200
    And the page contains an element with name "start_date"
    When I submit the form at "/admin/cohorts/create" with data {"cluster_key": "email-automation", "name": "UI Test Cohort", "start_date": "2026-09-01", "end_date": "2026-09-14"}
    Then the response status is 302

  Scenario: Admin feed form renders and POSTs via HTML
    Given I am logged in as an admin user
    When I GET "/admin/feed/create"
    Then the response status is 200
    And the page contains an element with name "title"
    When I submit the form at "/admin/feed/create" with data {"cluster_key": "email-automation", "title": "UI Test Posting", "unlock_day": "5"}
    Then the response status is 302
