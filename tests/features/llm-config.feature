Feature: LLM Config — Single Source of Truth
  As a developer
  I want all LLM provider settings resolved from one module
  So that changing models (big-pickle primary, deepseek fallback) touches one place

  Scenario: LC1 — Provider chain has big-pickle primary, deepseek fallback
    Given the LLM config module is loaded
    Then the provider chain should list exactly two providers
    And the primary provider should use model "big-pickle" via OpenCode.ai
    And the fallback provider should use model "deepseek-v4-flash-free" via OpenCode.ai

  Scenario: LC2 — Env vars override local config (Render deployment)
    Given environment variables LLM_API_URL, LLM_API_KEY, LLM_MODEL are set
    Then the provider chain should use those values for the primary provider
    And the fallback should use the same URL and key with model "deepseek-v4-flash-free"

  Scenario: LC3 — call_llm falls back to second provider on failure
    Given the primary provider fails with HTTP 500
    And the fallback provider succeeds
    Then call_llm should return the fallback provider's response
    And no exception should be raised

  Scenario: LC4 — call_llm returns None when all providers fail
    Given both providers fail
    Then call_llm should return None
    And callers fall back to structured content

  Scenario: LC5 — CLI curriculum generator uses the same module
    Given I run generate_full_curriculum.py
    Then it should resolve its URL, key, and model from services/llm_config
    And default to model "big-pickle" (not a hardcoded config read)

  Scenario: LC6 — API background generator uses the same module
    Given the /api/generate-curriculum endpoint starts a background thread
    Then it should resolve providers from services/llm_config
    And log which provider/model is being used
