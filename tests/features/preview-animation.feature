# Preview Animation — BDD Specification
# The TwoPanel preview must have dynamic, visible animations synced to audio.

Feature: Preview Animation Quality
  As a user watching the video preview
  I want dynamic visual animations that sync with audio progress
  So that the preview feels alive and educational

  Background:
    Given I am logged in

  Scenario: PA-1 — Step boxes exist with animation classes
    When I open the preview for day 1 of n8n-automation directly
    Then I should see 3 step boxes in the SVG diagram
    And each step box should have a CSS transition or animation property

  Scenario: PA-2 — Step boxes animate during audio playback
    When I open the preview for day 1 of n8n-automation directly
    And I play the preview audio for 3 seconds
    Then the step-0 box should have the "active" class
    And the other step boxes should not have the "active" class yet

  Scenario: PA-3 — Step boxes activate at the right progress
    When I open the preview for day 1 of n8n-automation directly
    And I play the preview audio to 50 percent progress
    Then step-1 box should have the "active" class
    And step-0 and step-2 boxes should not have the "active" class

  Scenario: PA-4 — Last step active at near-end progress
    When I open the preview for day 1 of n8n-automation directly
    And I play the preview audio to 90 percent progress
    Then step-2 box should have the "active" class
    And step-0 and step-1 boxes should not have the "active" class

  Scenario: PA-5 — Section progress dots sync with audio
    When I open the preview for day 1 of n8n-automation directly
    And I play the preview audio for 3 seconds
    Then section dot 0 should be active
    And section dots 1 and 2 should not be active

  Scenario: PA-6 — Dynamic labels come from curriculum content
    When I open the preview for day 1 of web-scraping-python directly
    Then the step box labels should not contain "Day 1 concept"
    And the step box labels should contain meaningful text

  Scenario: PA-7 — SVG fits within panel bounds (no clipping)
    When I open the preview for day 1 of n8n-automation directly
    Then the SVG viewBox should be "0 0 780 340"
    And all step boxes should have x-coordinates less than 780

  Scenario: PA-8 — Play/pause toggle works
    When I open the preview for day 1 of n8n-automation directly
    And I click the play button
    Then the play button should show pause icon
    When I click the play button again
    Then the play button should show play icon
