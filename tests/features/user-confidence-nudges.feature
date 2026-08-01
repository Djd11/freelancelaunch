Feature: User Confidence via Nudges & Daily Practice Feedback
  As a learner on the platform
  I want immediate feedback and encouragement when I complete daily practice
  So that I stay motivated and confident throughout my 30-day journey

  Background:
    Given I am a logged-in user enrolled in a cohort
    And I have a cohort_video for Day 1

  ─── PROGRESS TRACKING WORKS ──────────────────────────────

  Scenario: P1 — Marking video watched saves to database
    When I check "Watch today's video" on the dashboard
    Then a user_progress record should exist for me and Day 1
    And video_watched should be True

  Scenario: P2 — All 3 tasks complete the day
    When I check video watched, practice completed, and apply completed
    Then the day should be marked complete
    And a celebration message should appear: "🎉 Day 1 complete!"
    And the freelance_pipeline stage should advance from learning

  Scenario: P3 — Re-marking doesn't duplicate records
    When I check the same checkbox twice
    Then there should still be exactly 1 user_progress record
    And it should remain True

  ─── STREAK TRACKING ──────────────────────────────────────

  Scenario: S1 — Streak increments on consecutive days
    Given I completed Day 1
    When I complete Day 2 the next day
    Then my streak should be 2
    And the dashboard should show "🔥 2-day streak"

  Scenario: S2 — Streak resets after a missed day
    Given my last completion was 3 days ago
    When I complete today's day
    Then my streak should reset to 1

  Scenario: S3 — Streak survives same-day completion
    Given I complete Day 1 in the morning
    When I complete Day 2 in the evening
    Then my streak should be 2 (not reset)

  ─── ENCOURAGEMENT & NUDGES ───────────────────────────────

  Scenario: N1 — Positive feedback after each task
    When I check "Complete practice task"
    Then I should see a positive message (e.g., "Great work! Your practice is in.")
    And the message should reference what I completed

  Scenario: N2 — Milestone celebration at week boundaries
    Given I complete Day 7
    Then I should see "🏆 Week 1 Complete!"
    And encouragement for the next week

  Scenario: N3 — Nudge when practice is incomplete
    Given I am on Day 5
    And I haven't completed Day 4's practice
    Then the dashboard should nudge: "Don't forget Day 4's practice — you're so close!"
    And the nudge should be dismissible

  Scenario: N4 — Nudge for inactive users
    Given I haven't visited for 2 days
    When I log in
    Then I should see "👋 Welcome back! Day 3 awaits you"
    And my last completed day should be shown

  ─── CONFIDENCE METRICS ───────────────────────────────────

  Scenario: C1 — Dashboard shows completion percentage
    When I view the dashboard
    Then I should see "X/30 days completed"
    And a progress bar showing my percentage

  Scenario: C2 — Confidence score visible
    Given I have completed 10 days
    When I view the dashboard
    Then I should see a confidence/momentum score
    And it should be higher than a user who completed 2 days

  Scenario: C3 — All days in week are clickable
    When I view the weekly grid on dashboard
    Then each day should be a link to its detail page
    And completed days should show a checkmark or filled style
