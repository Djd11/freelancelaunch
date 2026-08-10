Feature: Phase A — Copy-Work (Days 1-5)
  As a sprinter
  I want to replicate real projects instead of passively watching videos
  So that I build muscle memory faster

  Scenario: A day serves a replication task from a real project
    Given an active sprint in phase A on day 2
    When I open the day view
    Then I see a copywork task with a source project to replicate
    And the task is sequenced as the 2nd of 3 replication projects

  Scenario: Phase A completes only after all 3 projects and gap-fill
    Given I have completed projects 1 and 2
    When I complete project 3 and the day 5 gap-fill lesson
    Then phase A is marked complete
    And phase B becomes available

  Scenario: Gap-fill detects the missing nuance
    Given my project 2 rubric flagged "mobile responsiveness"
    When I reach day 5
    Then I am served a targeted micro-lesson on mobile responsiveness

  Scenario: Phase B stays locked until phase A passes
    Given an active sprint in phase A with incomplete copywork
    When I try to open phase B
    Then I am shown the phase A completion gate
