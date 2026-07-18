Feature: Scheduler Cohort Discovery
  As the nightly scheduler
  I want to find active cohorts and determine the next video to produce
  So that every cohort gets their daily video on time

  Background:
    Given active cohorts exist in the database
    And some cohorts have videos already produced for tomorrow
    And some cohorts do not

  Scenario: Find active cohorts needing production
    When the scheduler runs nightly production
    Then it should find all active cohorts
    And it should determine tomorrow's day number for each cohort

  Scenario: Skip cohorts that already have ready videos
    Given a cohort where day 3 video is already "ready"
    When the scheduler checks day 3
    Then it should not re-produce the video
    And it should log that the video is already ready

  Scenario: Create cohort_video record if missing
    Given a cohort without a video record for day 5
    When the scheduler prepares day 5's production
    Then a new cohort_video record should be created
    And its production_status should be "pending"

  Scenario: Respect max_days boundary
    Given a cohort with max_days = 30 and current_day = 30
    When the scheduler checks if it should produce day 31
    Then it should skip production because day 31 > max_days
    And it should log that the cohort is completed
