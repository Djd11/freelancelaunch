Feature: Video Script Generation
  As the video pipeline
  I want to generate voiceover scripts and panel content
  So that each curriculum day produces a unique educational video

  Background:
    Given the LLM API is available
    And a topic "Web Scraping with Python"
    And a day title "Introduction to HTTP Requests"
    And a day description "Learn how HTTP requests work for web scraping"

  Scenario: Generate a complete voiceover script
    When the video script generator creates content
    Then the script should be a non-empty string
    And the script should contain words about the topic
    And the script should be approximately 250 words long

  Scenario: Generate exactly 9 panels
    When the video script generator creates content
    Then the panels array should have exactly 9 items
    And each panel should have an id, title, caption, color, and words
    And each panel should have a diagramType and graph configuration

  Scenario: Panels match script sections
    When the video script generator creates content
    Then the total word count across all panels should match the script word count

  Scenario: Each panel has valid graph data
    When the video script generator creates content
    Then each panel graph should have a valid type (bar, hbar, line, compare, nodes)
    And each graph should have labels, data, and unit fields
    And graph data should be an array of positive numbers

  Scenario: Fallback content when LLM is unavailable
    Given the LLM API is unavailable
    When the video script generator creates content
    Then content should still be generated using fallback logic
    And there should be exactly 9 panels
