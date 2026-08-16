Feature: Day View & Copy-Work (mockup screen 4)
  As a sprinter in Phase A
  I want a day view that sequences Watch → Copy → Apply with rubric verification and a gap-fill preview
  So that I build muscle memory by rebuilding real projects

  Background:
    Given the app is running against the live test database
    And a logged-in user
    Given I have an active sprint "s1" with 14 days for cluster "email-automation"

  Scenario: The day view renders the copy-work task spec
    Given I am on day 4 of sprint "s1"
    When I GET "/sprints/s1/day/4"
    Then the response status is 200
    And the page contains the text "Copy-Work"
    And the page contains the text "Rebuild the Abandoned-Cart Flow"

  Scenario: The lesson renders as an HTML preview with TTS, not an MP4
    When I GET "/sprints/s1/day/4"
    Then the page contains the text "TwoPanel"
    And the page does not contain the text "MP4"

  Scenario: A lesson with a voiceover renders the two-panel video player
    Given day 4 of sprint "s1" has a generated lesson with a voiceover
    When I GET "/sprints/s1/day/4"
    Then the response status is 200
    And the page contains an element with attribute "data-lesson-player"
    And the page contains the text "TwoPanel"

  Scenario: The lesson content is generated from the cluster's live job posting
    When I GET "/sprints/s1/day/4"
    Then the page contains the text "Klaviyo flow setup for store"
    And the page contains the text "how to"

  Scenario: The day view renders the generated copy-work anatomy (steps + rubric)
    When I GET "/sprints/s1/day/4"
    Then the page contains the text "Trigger on Checkout Started"
    And the page contains the text "auto-checked by verification service"

  Scenario: The content generation progress is reported as a DB-backed count
    When I GET "/sprints/s1/generation"
    Then the response status is 200
    And the JSON has field "total" equal to 14
    And the JSON path "generated" is an integer

  Scenario: A completed day shows the unlock uptick banner
    Given day 4 of sprint "s1" is marked done
    And the meter for sprint "s1" has unlocked 186 of 450 with delta 38
    When I GET "/sprints/s1/day/4"
    Then the page contains the text "job postings unlocked"
    And the page contains the text "+38"

  Scenario: Gap-Fill preview surfaces the auto-detected nuance before Day 5
    Given copy-work project 2 for sprint "s1" flagged gap-fill topic "mobile responsiveness"
    When I GET "/sprints/s1/day/4"
    Then the page contains the text "Gap-Fill"
    And the page contains the text "mobile responsiveness"

  Scenario: Submitting the copy-work task runs the rubric check
    When I submit the copy-work task for day 4 of sprint "s1" with rubric_url "https://github.com/me/flow"
    Then the response status is 302
    And a verification review for gate "A" is recorded for sprint "s1"

  Scenario: All three copy-work projects done with a passed gate unlocks Phase B
    Given copy-work projects 1, 2, and 3 for sprint "s1" are done
    And Phase A has passed verification for sprint "s1"
    When I GET "/sprints/s1"
    Then Phase B is not locked

  Scenario: A day view for a missing sprint redirects to the dashboard
    When I GET "/sprints/does-not-exist/day/4"
    Then the response redirects to "/dashboard/"
