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

  Scenario: Submitting a fully self-checked project completes the Replicate check-item
    Given I am on day 4 of sprint "s1"
    And I check all rubric items for project 2 of sprint "s1"
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

  # ── #7 rubric checkboxes are the LEARNER's self-check, never auto-passed ──
  Scenario: Rubric checkboxes persist as the learner left them after submitting
    Given I am on day 4 of sprint "s1"
    And copy-work project 2 for sprint "s1" has a 3-point rubric
    When I GET "/sprints/s1/day/4"
    Then the page contains at least 3 rubric checkboxes
    And the rubric checkboxes are not checked
    When I check all rubric items for project 2 of sprint "s1"
    And I GET "/sprints/s1/day/4"
    Then the rubric checkboxes are all checked
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

  # ── Interactive Rubric Checkboxes (Gap 1) ─────────────────────────────────
  Scenario: Rubric checkboxes are interactive (not disabled) and user-checkable
    Given I am on day 4 of sprint "s1"
    And copy-work project 2 for sprint "s1" has a 3-point rubric
    When I GET "/sprints/s1/day/4"
    Then the page contains at least 3 rubric checkboxes
    And the rubric checkboxes are not disabled
    And the rubric checkboxes are not checked
    When I check the first rubric checkbox for project 2 of sprint "s1"
    And I GET "/sprints/s1/day/4"
    Then the first rubric checkbox is checked

  Scenario: Dashboard "Self-check vs rubric" reflects actual rubric item completion
    Given I am on day 4 of sprint "s1"
    And copy-work projects 1, 2, and 3 for sprint "s1" are done
    And copy-work project 1 for sprint "s1" has all 3 rubric items user-checked
    And copy-work project 2 for sprint "s1" has all 3 rubric items user-checked
    And copy-work project 3 for sprint "s1" has all 3 rubric items user-checked
    When I GET "/sprints/s1"
    Then the check-item "Self-check vs rubric" is marked done
    # If any project lacks a user-checked rubric item, the dashboard check-item stays unchecked
    Given copy-work project 1 for sprint "s1" has only 2 of 3 rubric items user-checked
    When I GET "/sprints/s1"
    Then the check-item "Self-check vs rubric" is not marked done

  # ── Case Study Validation (Gap 3) ──────────────────────────────────────────
  Scenario: "Case study written" requires Problem, Solution, and Result all filled
    Given I have an active sprint "s1" with 14 days for cluster "email-automation"
    And a job cluster "email-automation" with 5 active postings
    And a case study "Incomplete Study" exists for sprint "s1" with empty result
    When I submit the contract form to "/sprints/s1/contract/submit" with submission_url "https://dropbox.com/x"
    And I GET "/sprints/s1/contract"
    Then the check-item "Case study written" is not marked done
    And the check-item "Automated flow check" is marked done

  Scenario: Case study with all three fields marks "Case study written" as done
    Given I have an active sprint "s1" with 14 days for cluster "email-automation"
    And a job cluster "email-automation" with 5 active postings
    And a case study "Complete Study" exists for sprint "s1" with problem, solution, and result filled
    When I submit the contract form to "/sprints/s1/contract/submit" with submission_url "https://dropbox.com/x"
    And I GET "/sprints/s1/contract"
    Then the check-item "Case study written" is marked done
    And the check-item "Automated flow check" is marked done

  # ── Gap-Fill User Confirmation (Gap 4) ─────────────────────────────────────
  Scenario: Gap-Fill preview has a user-confirmable check-item
    Given copy-work project 2 for sprint "s1" flagged gap-fill topic "mobile responsiveness"
    When I GET "/sprints/s1/day/4"
    Then the page contains a check-item "Gap-fill addressed"
    And the check-item "Gap-fill addressed" is not marked done
    When I mark the gap-fill addressed for day 4 of sprint "s1"
    And I GET "/sprints/s1/day/4"
    Then the check-item "Gap-fill addressed" is marked done

  # ── Individual Rubric Item Tracking (Gap 5) ────────────────────────────────
  Scenario: Individual rubric items are tracked per project
    Given copy-work project 2 for sprint "s1" has a 3-point rubric
    When I check the first rubric checkbox for project 2 of sprint "s1"
    And I check the second rubric checkbox for project 2 of sprint "s1"
    And I GET "/sprints/s1/day/4"
    Then the first rubric checkbox is checked
    And the second rubric checkbox is checked
    And the third rubric checkbox is not checked
