# Curriculum Quality Gate — BDD Specification
# Bad/duplicate content must NEVER reach the database.
# The system must validate curriculum quality BEFORE saving.

Feature: Curriculum Quality Gate
  As a platform owner
  I want the system to reject low-quality or duplicate curriculum content
  So that users never see wrong or repeated content

  # ── Validation: content must pass quality checks before DB save ──

  Scenario: QG-1 — Improved fallback generates quality content that passes validation
    When I generate a fallback curriculum for "test-topic" with 5 days
    Then the fallback curriculum should pass quality validation
    And no fallback day should have a "Part <number>" title pattern

  Scenario: QG-2 — Duplicate descriptions are rejected
    When I check these descriptions for uniqueness:
      | description                          |
      | Learn n8n automation basics           |
      | Learn n8n automation basics           |
      | Build advanced n8n workflows          |
    Then the uniqueness check should fail with 1 duplicate(s)

  Scenario: QG-3 — Unique descriptions pass validation
    When I check these descriptions for uniqueness:
      | description                          |
      | Learn n8n automation basics           |
      | Build advanced n8n workflows          |
      | Deploy n8n to production              |
    Then the uniqueness check should pass

  Scenario: QG-4 — Generic titles are rejected
    When I validate these titles:
      | title                                          |
      | Day 1: n8n Workflow Automation — Part 1        |
      | Day 2: n8n Workflow Automation — Part 2        |
    Then all titles should be rejected as generic

  Scenario: QG-5 — Meaningful titles pass validation
    When I validate these titles:
      | title                                          |
      | Setting Up Your First n8n Workflow              |
      | HTTP Requests and Webhooks in n8n              |
      | Building a Multi-Step Automation Pipeline       |
    Then all titles should pass validation

  Scenario: QG-6 — Curriculum generation endpoint validates before save
    Given I am logged in
    When I request curriculum generation for a topic with existing bad data
    Then the system should not overwrite with fallback content
    And the response should indicate quality validation occurred

  # ── Regenerate capability ──

  Scenario: QG-7 — Day page shows regenerate option when content is fallback
    Given I am logged in
    When I visit a day page with fallback content
    Then I should see a "Regenerate Lesson" option

  Scenario: QG-8 — Day page shows content status
    Given I am logged in
    When I visit a day page with real curriculum content
    Then I should not see a "Regenerate Lesson" option
