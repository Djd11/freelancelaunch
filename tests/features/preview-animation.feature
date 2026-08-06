# Preview Animation — BDD Specification
# The single-panel preview must show kinetic word-by-word text synced to voice-over audio.

Feature: Preview Animation Quality
  As a user watching the video preview
  I want kinetic text that animates word-by-word in sync with audio
  So that the preview feels alive and educational

  Background:
    Given I am logged in

  Scenario: PA-1 — Single panel layout with kinetic text
    When I open the preview for day 1 of web-scraping-python directly
    Then I should see a single panel layout
    And the panel should contain kinetic word spans
    And there should be no SVG diagram step boxes

  Scenario: PA-2 — Words reveal during audio playback
    When I open the preview for day 1 of web-scraping-python directly
    And I play the preview audio for 3 seconds
    Then some kinetic words should be visible
    And some kinetic words should still be hidden

  Scenario: PA-3 — More words reveal at 50 percent progress
    When I open the preview for day 1 of web-scraping-python directly
    And I play the preview audio to 50 percent progress
    Then the first half of kinetic words should be visible
    And the last half of kinetic words should still be hidden

  Scenario: PA-4 — All words visible at near-end progress
    When I open the preview for day 1 of web-scraping-python directly
    And I play the preview audio to 90 percent progress
    Then most kinetic words should be visible

  Scenario: PA-5 — Dynamic title from curriculum content
    When I open the preview for day 1 of web-scraping-python directly
    Then the preview title should not be empty
    And the preview title should contain meaningful text

  Scenario: PA-6 — Play/pause toggle works
    When I open the preview for day 1 of web-scraping-python directly
    And I click the play button
    Then the play button should show pause icon
    When I click the play button again
    Then the play button should show play icon

  Scenario: PA-7 — Single panel has no left diagram panel
    When I open the preview for day 1 of web-scraping-python directly
    Then there should be no left diagram panel
    And there should be no section progress dots
