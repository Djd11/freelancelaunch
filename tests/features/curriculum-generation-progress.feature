Feature: Curriculum Generation with Day-by-Day Progress
  As an enrolled user
  I want to generate my 30-day curriculum with real-time progress
  So that I can see each day being created and track generation status

  Background:
    Given I am logged in and enrolled in "Web Scraping with Python"
    And no curriculum exists for this topic

  Scenario: G1 — Generate button visible when curriculum missing
    When I visit the topic detail page
    Then I should see "Your 30-day curriculum hasn't been generated yet"
    And I should see a "🎯 Generate My 30-Day Curriculum" button

  Scenario: G2 — Clicking generate starts background job
    When I click the generate button
    Then the button should be replaced by a progress bar
    And I should see "Starting generation..." label
    And the API should return status "started"

  Scenario: G3 — Progress bar shows real-time day count
    Given generation is running
    When I poll /api/generation-status/web-scraping-python
    Then the response should include current_day (1-30)
    And the response should include total_days (30)
    And the response should include status "generating"
    And the progress percent should match current_day / total_days * 100

  Scenario: G4 — Each day saved to database during generation
    Given generation is running
    When I query curriculum_days table
    Then the count should match the current_day from progress
    And each saved day should have: title, description, practice_task, apply_task

  Scenario: G5 — Generation complete triggers page reload
    Given all 30 days have been generated
    When I poll /api/generation-status/web-scraping-python
    Then the status should be "complete"
    And percent should be 100
    And the frontend should reload to show the full curriculum

  Scenario: G6 — Error handling shows message
    Given generation fails on day 5
    When I poll /api/generation-status/web-scraping-python
    Then status should be "error"
    And error message should be displayed in the UI

  Scenario: G7 — LLM API configuration is used
    Given the system has LLM_API_URL configured
    When curriculum generation starts
    Then it should use the configured LLM API endpoint
    And pass the configured API key
    And use the configured model name

  Scenario: G8 — Already generated curricula are not re-generated
    Given 30 curriculum days already exist
    When I click the generate button
    Then the API should return status "complete" immediately
    And no new days should be created

  Scenario: G9 — Progress shows current day title
    Given day 15 of 30 is being generated
    When I poll for status
    Then current_day should be 15
    And last_title should contain the day's lesson title
    And the UI should display "Generating Day 15 of 30"
