Feature: Hardened Verification Gates — required URLs & case study (fixes #4, #5, #6)
  As a sprinter
  I want copy-work and deliverable submissions to require real, valid URLs,
  and Gate B to require a case study,
  So that gates only pass on genuine evidence, not on empty or placeholder clicks

  Background:
    Given the app is running against the live test database
    And a logged-in user
    Given I have an active sprint "s1" with 14 days for cluster "email-automation"
    And a job cluster "email-automation" with 5 active postings

  # ── #4: copy-work submission requires a valid URL ──────────────────
  Scenario: Copy-work submission with an empty URL is rejected
    When I POST to "/sprints/s1/day/2/copywork"
    Then the response status is 302
    And the flash message mentions "Paste a link"
    And copy-work project 1 for sprint "s1" is not marked done
    And gate "A" has not passed verification for sprint "s1"

  Scenario: Copy-work submission with a scheme-less URL is rejected
    When I submit the copy-work task for day 2 of sprint "s1" with rubric_url "github.com/me/flow"
    Then the response status is 302
    And the flash message mentions "valid link"
    And copy-work project 1 for sprint "s1" is not marked done
    And gate "A" has not passed verification for sprint "s1"

  Scenario: Copy-work submission with a valid URL stores it on the project
    When I submit the copy-work task for day 2 of sprint "s1" with rubric_url "https://github.com/me/flow"
    Then the response status is 302
    And copy-work project 1 for sprint "s1" has submitted_url "https://github.com/me/flow"

  # ── #5: Gate A requires all three projects to have submitted URLs ──
  Scenario: Gate A does not pass when a done project is missing its submitted URL
    Given copy-work projects 1, 2, and 3 for sprint "s1" are done
    And copy-work project 1 for sprint "s1" has its submitted URL removed
    When I submit the copy-work task for day 4 of sprint "s1" with rubric_url "https://github.com/me/flow"
    Then the response status is 302
    And gate "A" has not passed verification for sprint "s1"

  # ── Gate A requires learner self-checks — the rubric never auto-passes itself
  Scenario: Copy-work submission without all rubric self-checks does not count done
    Given copy-work project 1 for sprint "s1" has only 2 of 3 rubric items user-checked
    When I submit the copy-work task for day 2 of sprint "s1" with rubric_url "https://github.com/me/flow"
    Then the response status is 302
    And the flash message mentions "rubric"
    And copy-work project 1 for sprint "s1" is not marked done
    And gate "A" has not passed verification for sprint "s1"

  Scenario: Re-submitting a done project without full self-checks un-marks it
    Given copy-work projects 1, 2, and 3 for sprint "s1" are done
    And copy-work project 3 for sprint "s1" has only 2 of 3 rubric items user-checked
    When I submit the copy-work task for day 5 of sprint "s1" with rubric_url "https://github.com/me/p3"
    Then the response status is 302
    And copy-work project 3 for sprint "s1" is not marked done
    And gate "A" has not passed verification for sprint "s1"

  Scenario: Gate A passes when all three done projects have submitted URLs
    Given copy-work projects 1, 2, and 3 for sprint "s1" are done
    When I submit the copy-work task for day 4 of sprint "s1" with rubric_url "https://github.com/me/flow"
    Then the response status is 302
    And gate "A" has passed verification for sprint "s1"

  # ── #6: Gate B validates URL format and requires a case study ──────
  Scenario: Deliverable submission with a scheme-less URL does not pass Gate B
    When I submit the contract form to "/sprints/s1/contract/submit" with submission_url "dropbox.com/x"
    Then the response status is 302
    And the flash message mentions "valid link"
    And gate "B" has not passed verification for sprint "s1"

  Scenario: Deliverable submission with a valid URL but no case study does not pass Gate B
    When I submit the contract form to "/sprints/s1/contract/submit" with submission_url "https://dropbox.com/x"
    Then the response status is 302
    And a verification review for gate "B" is recorded for sprint "s1"
    And gate "B" has not passed verification for sprint "s1"

  Scenario: Deliverable submission with a valid URL and a case study passes Gate B
    When I save the case study "Abandoned-Cart Recovery Flow" for sprint "s1"
    And I submit the contract form to "/sprints/s1/contract/submit" with submission_url "https://dropbox.com/x"
    Then the response status is 302
    And gate "B" has passed verification for sprint "s1"
