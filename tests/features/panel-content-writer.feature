Feature: PanelContent.js Writer
  As the video pipeline
  I want to generate valid PanelContent.js files
  So that Remotion can render videos from them

  Background:
    Given generated panel data with 9 panels
    And a temporary output directory

  Scenario: Write PanelContent.js to disk
    When the panel content writer creates the file
    Then a PanelContent.js file should exist at the output path
    And the file should contain JavaScript module exports

  Scenario: PanelContent.js exports required constants
    When the panel content writer creates the file
    Then the file should export PANELS array
    And the file should export TOTAL_FRAMES constant
    And the file should export VIDEO_SECONDS constant
    And the file should export PHASE_STARTS array
    And the file should export KEYWORDS set

  Scenario: Timing calculations are valid
    When the panel content writer creates the file
    Then VIDEO_SECONDS should be a positive number matching ~TOTAL_WORDS/2.5
    And GAP_FRAMES should equal (PANELS.length - 1) * 10
    And TOTAL_FRAMES should approximately equal VIDEO_SECONDS * 30
    And each DURATIONS entry should be >= 30 frames

  Scenario: PANELS array has required structure
    When the panel content writer creates the file
    Then each panel should have: id, title, caption, color, accent, diagramType, words, graph
    And the words field should be a non-empty string
    And the color should be a valid hex color

  Scenario: Update KEYWORDS in TwoPanelStack.jsx
    Given a TwoPanelStack.jsx file with default keywords
    When the writer updates keywords with ["Web", "Scraping", "HTTP", "Request"]
    Then the file should contain the new keywords
    And the file should not contain the old default keywords
