Feature: Check-Items — every checkbox/check-item reflects verified state, not decoration
  As a sprinter
  I want each check-item on the day view, dashboard, and contract page to be driven by
  real verified state (lesson watched, project done, Gate A/B, case study)
  So that no checklist affordance is decorative, dead, or out of spec (eng-spec J4/J5)

  Background:
    Given the app is running against the live test database
    And a logged-in user
    Given I have an active sprint "s1" with 14 days for cluster "email-automation"
    And a job cluster "email-automation" with 5 active postings

  # ── #1 day-view check-items are wired to real state ───────────────────────
  Scenario: A fresh day view leaves every check-item unchecked
    Given I am on day 4 of sprint "s1"
    When I GET "/sprints/s1/day/4"
    Then the response status is 200
    And the check-item "Mark lesson watched" is not marked done
    And the check-item "Replicate from scratch" is not marked done
    And the check-item "Pass 3-point rubric" is not marked done

  Scenario: Marking the lesson watched completes the day-view check-item
    Given I am on day 4 of sprint "s1"
    When I mark the lesson watched for day 4 of sprint "s1"
    And I GET "/sprints/s1/day/4"
    Then the check-item "Mark lesson watched" is marked done
    And the check-item "Replicate from scratch" is not marked done
    And the check-item "Pass 3-point rubric" is not marked done

  Scenario: Submitting copy-work completes the Replicate check-item (not the rubric yet)
    Given I am on day 4 of sprint "s1"
    When I submit the copy-work task for day 4 of sprint "s1" with rubric_url "https://github.com/me/flow"
    And I GET "/sprints/s1/day/4"
    Then the check-item "Replicate from scratch" is marked done
    And the check-item "Pass 3-point rubric" is not marked done

  Scenario: Passing Gate A completes the rubric check-item
    Given I am on day 4 of sprint "s1"
    And copy-work projects 1, 2, and 3 for sprint "s1" are done
    When I submit the copy-work task for day 4 of sprint "s1" with rubric_url "https://github.com/me/flow"
    And I GET "/sprints/s1/day/4"
    Then the check-item "Pass 3-point rubric" is marked done

  # ── #7 rubric is auto-checked by the verification service (not a dead <ul>) ─
  Scenario: Submitting copy-work auto-checks the rubric checkboxes
    Given I am on day 4 of sprint "s1"
    And copy-work project 2 for sprint "s1" has a 3-point rubric
    When I GET "/sprints/s1/day/4"
    Then the page contains at least 3 rubric checkboxes
    And the rubric checkboxes are not checked
    When I submit the copy-work task for day 4 of sprint "s1" with rubric_url "https://github.com/me/flow"
    And I GET "/sprints/s1/day/4"
    Then the rubric checkboxes are all checked

  # ── #2 dashboard Today card check-items are wired ────────────────────────
  Scenario: A fresh dashboard leaves Today's check-items unchecked
    When I GET "/sprints/s1"
    Then the check-item "Watch lesson" is not marked done
    And the check-item "Replicate the project" is not marked done
    And the check-item "Self-check vs rubric" is not marked done

  Scenario: A watched lesson marks the dashboard Watch-lesson as done
    Given I am on day 4 of sprint "s1"
    And day 4 of sprint "s1" has the lesson marked watched
    When I GET "/sprints/s1"
    Then the check-item "Watch lesson" is marked done

  # ── #3 contract verification check-items are wired ────────────────────────
  Scenario: A fresh contract page leaves both verification check-items unchecked
    When I GET "/sprints/s1/contract"
    Then the response status is 200
    And the check-item "Automated flow check" is not marked done
    And the check-item "Case study written" is not marked done

  Scenario: Submitting a deliverable and a case study passes the verification check-items
    When I save the case study "Abandoned-Cart Recovery Flow" for sprint "s1"
    And I submit the contract form to "/sprints/s1/contract/submit" with submission_url "https://dropbox.com/x"
    And I GET "/sprints/s1/contract"
    Then the check-item "Automated flow check" is marked done
    And the check-item "Case study written" is marked done

  # ── #7 gap-fill remains deterministic per eng-spec §5 (v1) ────────────────
  Scenario: Gap-Fill preview surfaces the deterministic nuance before Day 5
    Given copy-work project 2 for sprint "s1" flagged gap-fill topic "mobile responsiveness"
    When I GET "/sprints/s1/day/4"
    Then the page contains the text "Gap-Fill"
    And the page contains the text "mobile responsiveness"
