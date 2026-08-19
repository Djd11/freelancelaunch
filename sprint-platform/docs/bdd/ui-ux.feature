Feature: UI/UX — every page's CTAs work end to end (no dead ends, no fake functionality)
  As a user
  I want every button, link, and form on every page to do what it promises
  So that the web app is seamless — nothing is a broken landing or fake functionality

  Background:
    Given the app is running against the live test database
    And a logged-in user
    Given I have an active sprint "s1" with 14 days for cluster "email-automation"
    And a job cluster "email-automation" with 5 active postings

  # ── LANDING (public) ──────────────────────────────────────────────
  Scenario: Landing — every nav and hero CTA is present
    When I GET "/"
    Then the response status is 200
    And the page contains a link to "/sprints"
    And the page contains a link to "/topics"
    And the page contains a link to "/pricing"
    And the page contains the text "Start your sprint"
    And the page contains the text "See how it works"

  Scenario: Landing — the Topics and Pricing CTAs resolve
    When I GET "/topics"
    Then the response status is 302
    And the response redirects to "/sprints"
    When I GET "/pricing"
    Then the response status is 200
    And the page contains the text "Start free"

  Scenario: Landing — the Start CTA leads a visitor to login, not a dead end
    Given I am not logged in
    When I GET "/"
    And I GET "/sprints"
    Then the response status is 302
    And the response redirects to "/auth/login"

  # ── SPRINT PICKER ─────────────────────────────────────────────────
  Scenario: Picker — Start sprint CTA creates a working sprint
    When I GET "/sprints"
    Then the response status is 200
    And the page contains a link to start a sprint for "email-automation"
    When I POST to the start-sprint form for cluster "email-automation"
    Then I can open the created sprint dashboard
    And the page contains the text "Email Automation Sprint"
    And the page contains the text "Job Unlock Meter"

  Scenario: Picker — Request-a-sprint CTA records the skill
    When I submit a request-a-sprint form for skill "notion-automation"
    Then the response status is 302
    And a job cluster "notion-automation" is recorded as requested

  Scenario: Picker — Sign out CTA ends the session
    When I GET "/auth/logout"
    Then the response status is 302
    And the response redirects to "/"
    When I GET "/sprints"
    Then the response status is 302
    And the response redirects to "/auth/login"

  # ── SPRINT DASHBOARD ──────────────────────────────────────────────
  Scenario: Dashboard — Open Day CTA opens the day view
    When I GET "/sprints/s1"
    Then the response status is 200
    And the page contains the text "Open Day 4"
    When I GET "/sprints/s1/day/4"
    Then the response status is 200
    And the page contains the text "Copy-Work"

  Scenario: Dashboard — Profile and Mentor nav CTAs resolve
    When I GET "/sprints/s1"
    Then the page contains a link to "/profile/me"
    And the page contains a link to "/mentor"

  Scenario: Dashboard — Complete sprint CTA finishes the sprint
    When I POST to "/sprints/s1/complete"
    Then the response status is 302
    And sprint "s1" is completed

  Scenario: Dashboard — Record-a-contract CTA rolls up earnings
    When I GET "/sprints/s1"
    Then the response status is 200
    And the page contains the text "Record a contract"
    When I add a contract of value 300 with 20 hours on platform "upwork" for sprint "s1"
    Then sprint "s1" has contracts_won equal to 1
    And sprint "s1" has total_earned equal to 300

  # ── DAY VIEW ──────────────────────────────────────────────────────
  Scenario: Day view — the Dashboard link and Submit-for-check CTA work
    When I GET "/sprints/s1/day/4"
    Then the response status is 200
    And the page contains the text "← Dashboard"
    And the page contains the text "Submit for check"
    When I submit the copy-work task for day 4 of sprint "s1" with rubric_url "https://github.com/me/flow"
    Then the response status is 302
    And a verification review for gate "A" is recorded for sprint "s1"

  Scenario: Day view — the Mark-day-complete CTA advances the sprint
    When I GET "/sprints/s1/day/4"
    Then the page contains the text "Mark day 4 complete"
    When I POST to "/sprints/s1/day/4/complete"
    Then the response status is 302
    And the response redirects to a day page
    And the sprint "s1" is now on day 5

  # ── MOCK CONTRACT ─────────────────────────────────────────────────
  Scenario: Contract — deliverable submit and case-study CTAs work
    When I GET "/sprints/s1/contract"
    Then the response status is 200
    And the page contains the text "Submit deliverable for verification"
    And the page contains the text "Save case study"
    When I save the case study "Abandoned-Cart Recovery Flow" for sprint "s1"
    Then a case study titled "Abandoned-Cart Recovery Flow" exists for sprint "s1"
    When I submit the contract form to "/sprints/s1/contract/submit" with submission_url "https://dropbox.com/x"
    Then the response status is 302
    And gate "B" has passed verification for sprint "s1"

  # ── PROPOSALS ─────────────────────────────────────────────────────
  Scenario: Proposals — the locked page links to the Mock Contract
    Given Phase B has not passed verification for sprint "s1"
    When I GET "/sprints/s1/proposals"
    Then the response status is 200
    And the page contains the text "Open the Mock Contract"

  Scenario: Proposals — draft submit and outcome-log CTAs work
    Given Phase B has passed verification for sprint "s1"
    And a draft proposal "p1" exists for job "email-automation-1" on sprint "s1"
    When I GET "/sprints/s1/proposals"
    Then the page contains the text "First-Bid"
    When I choose platform "upwork" and submit the proposal form to "/sprints/s1/proposals/p1/submit"
    Then the proposal "p1" is submitted on platform "upwork"
    When I log outcome "response" for proposal "p1" on sprint "s1"
    Then sprint "s1" has responses_received equal to 1

  Scenario: Proposals — the Copy proposal CTA is wired, no dead links remain
    Given Phase B has passed verification for sprint "s1"
    When I GET "/sprints/s1/proposals"
    Then the page contains an element with attribute "data-copy-proposal"
    And the page does not contain any dead link

  # ── MENTOR ────────────────────────────────────────────────────────
  Scenario: Mentor — a turn is recorded and the exchange renders on the page
    When I POST to "/mentor/turn" with JSON {"question": "How do I recover abandoned carts?"}
    Then the response status is 200
    And the JSON has field "answer" present
    When I GET "/mentor"
    Then the response status is 200
    And the page contains the text "How do I recover abandoned carts?"

  # ── PROFILE / CLIENTS / PRICING ───────────────────────────────────
  Scenario: Profile — nav CTAs resolve (public page)
    When I GET "/profile/maya"
    Then the response status is 200
    And the page contains a link to "/sprints"
    And the page contains a link to "/mentor"
    And the page contains a link to "/clients/freelancers"

  Scenario: Clients — the filter form resolves
    When I GET "/clients/freelancers?cluster=email-automation&within_days=30"
    Then the response status is 200
    And the page contains the text "Filter"
    And the page contains the text "Fresh, verified freelancers"

  Scenario: Pricing — the Start free CTA resolves for a logged-in user
    When I GET "/pricing"
    Then the response status is 200
    And the page contains a link to "/sprints"
    When I GET "/sprints"
    Then the response status is 200
    And the page contains the text "Choose your sprint"
