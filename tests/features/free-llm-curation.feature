Feature: Free LLM Content Curation Pipeline
  As the platform
  I want to curate 30-day curriculum content using free LLM providers
  So that content generation costs $0 and works for any topic

  Background:
    Given the curriculum generator service is available

  Scenario: G1 — Generates curriculum for any topic name
    When I run the curriculum generator for "Video Editing"
    Then it should produce 30 daily lessons
    And each lesson should have a title
    And each lesson should have all 6 content sections
    And no lesson should contain fallback placeholder text

  Scenario: G2 — Weekly themes structure the curriculum
    When a curriculum is generated for a topic
    Then days 1-7 should cover Foundation concepts
    And days 8-14 should cover Building concepts
    And days 15-21 should cover Application concepts
    And days 22-30 should cover Mastery concepts

  Scenario: G3 — Content is topic-specific (not generic)
    When I generate curriculum for "Machine Learning"
    Then lesson titles should mention ML concepts (models, training, data)
    And practice tasks should be ML-specific
    And no lesson should mention unrelated topics (e.g., "video editing")

  Scenario: G4 — Uses free LLM provider automatically
    When curriculum generation starts
    Then it should attempt OpenRouter free model first
    And fall back to Omniroute if OpenRouter unavailable
    And fall back to configured LLM_API_URL if others fail
    And use graceful fallback content only as last resort

  Scenario: G5 — Handles rate limits with retry
    Given the LLM provider returns HTTP 429 (rate limited)
    When I retry the request
    Then it should wait and retry up to 3 times
    And eventually succeed or report the failure

  Scenario: G6 — Generates within token budget
    When I generate one day's lesson
    Then the LLM request should use less than 2000 output tokens
    And the response should fit in one request (no pagination needed)

  Scenario: G7 — Quality gate validates content
    When a lesson is generated
    Then it should be scored against 10 quality criteria
    And lessons scoring below 75/100 should be regenerated
    And the final lesson should pass quality checks

  Scenario: G8 — Output is database-ready
    When a lesson is generated
    Then it should have fields: title, hook, concept, practice, retrieval, spaced_review, preview
    And it should save cleanly to curriculum_days table
    And it should be renderable in the day detail template

  Scenario: G9 — Zero cost generation
    When the generator uses OpenRouter free model
    Then the provider should be :free suffix model
    And no paid API key should be required for MVP scale
    And a 30-day curriculum should cost $0
