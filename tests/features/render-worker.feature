Feature: Render Worker Orchestration
  As the video pipeline
  I want the render worker to orchestrate the full production flow
  So that videos are produced completely and error-free

  Background:
    Given a cohort_video record in the database with day_number 1
    And the video pipeline directory exists with node_modules installed
    And the topic is "web-scraping-python"

  Scenario: Full production pipeline succeeds
    When the render worker produces the day's video
    Then the script generation step should complete
    And the TTS audio file should be created at public/audio/narration.mp3
    And the PanelContent.js should be written
    And the Remotion render should produce an MP4 file
    And the YouTube metadata should be generated
    And the cohort_video status should be updated to "ready"

  Scenario: Production failure is handled gracefully
    Given the TTS command will fail
    When the render worker produces the day's video
    Then the cohort_video status should be "failed"
    And the error_message should contain details
    And the video_production_log should have the failure recorded

  Scenario: Database status updates through pipeline stages
    When the render worker produces the day's video
    Then the production log should contain entries for:
      | scripting |
      | rendering |
      | uploading |
      | ready     |
