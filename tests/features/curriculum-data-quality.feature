# Curriculum Data Quality — BDD Specification
# Each day must have unique, meaningful content — not generic fallback.
#
# The _fallback_lesson() is used when the LLM is unavailable. It must still
# produce day-specific content so every day feels distinct.

Feature: Curriculum Data Quality
  As a learner going through 30-day courses
  I want each day to have unique, meaningful content
  So that I'm not reading the same description on every day

  Scenario: CQ-1 — Descriptions are unique across all 30 days
    When I query the curriculum for n8n-automation from the database
    Then every day must have a unique description
    And no two days share identical description text

  Scenario: CQ-2 — Practice tasks vary across the curriculum
    When I query the curriculum for n8n-automation from the database
    Then at least 15 different unique practice_task values must exist
    And no practice_task should be "Complete the following exercise"

  Scenario: CQ-3 — Titles do not follow the generic "Part X" pattern
    When I query the curriculum for n8n-automation from the database
    Then no title should match "Part <number>"
    And no title should be only "Core Concepts"

  Scenario: CQ-4 — Descriptions contain topic-specific content
    When I query the curriculum for n8n-automation from the database
    Then at least 20 of 30 days should mention the topic name or related terms
    And descriptions should vary in length (not all identical char count)

  Scenario: CQ-5 — Apply tasks are day-specific
    When I query the curriculum for n8n-automation from the database
    Then every day must have a non-empty apply_task
    And at least 10 different unique apply_task values must exist

  Scenario: CQ-6 — Fallback lesson has day-specific content
    When I generate a fallback curriculum for "test-topic" with 5 days
    Then day 1 title should differ from day 2 title
    And day 1 description should differ from day 2 description
    And day 3 practice_task should differ from day 4 practice_task
    And all titles should contain their day number
