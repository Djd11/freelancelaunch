Feature: Job Unlock Meter
  As a sprinter
  I want to see live job postings "unlock" as I complete each day
  So that I feel immediate, concrete progress toward the client payoff

  Background:
    Given an email-automation cluster with 450 active job postings
    And a sprint with 14 days in phase A

  Scenario: The meter shows a quick-win uptick on Day 1 completion
    Given the sprint has completed 0 days
    When I complete day 1
    Then the unlock engine recomputes unlocked postings
    And the meter shows a positive delta on day 1
    And the meter shows day 1 unlocks a quick-win batch (>= 30 postings)
    And a snapshot is written to sprint_unlock_snapshots

  Scenario: Each completed day increases the unlocked count
    Given the sprint has completed 4 days (unlocked 186 postings)
    When I complete day 5
    Then the unlocked count increases
    And the meter shows the cumulative total as "unlocked / 450"

  Scenario: Escalating value — later days unlock fewer, higher-value postings
    Given a 450-posting cluster bucketed with the quick-win + escalating curve
    When I inspect the unlock_day distribution
    Then day 1 and 2 unlock the most postings (quick wins)
    And days 12 to 14 unlock the fewest, highest-value postings

  Scenario: The meter is O(1) to render
    Given a sprint with a saved snapshot in sprint_unlock_snapshots
    When I load the sprint dashboard
    Then the meter reads from the snapshot, not a live count

  Scenario: The meter stays anti-despondent through the valley of despair
    Given the sprint is on day 8 (phase B)
    When I complete day 8
    Then the uptick is prominent and the distance to the full cluster visibly shrinks
