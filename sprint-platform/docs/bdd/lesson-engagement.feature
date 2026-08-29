Feature: Day View Engagement Preview — hook · overview · usefulness · pre-quiz
  As a learner about to watch a lesson
  I want a punchy hook, a "what you'll learn" overview, a "why this matters" note,
  and a before-you-watch pre-quiz rendered ABOVE the lesson player
  So that I'm engaged and primed before the TwoPanel video plays — without breaking
  legacy lessons that predate these fields or the existing content-quality checks

  Background:
    Given the app is running against the live test database
    And a logged-in user
    Given I have an active sprint "s1" with 14 days for cluster "email-automation"
    And a job cluster "email-automation" with 5 active postings

  Scenario: The day view renders the engagement preview block above the player
    When the content generation worker runs for sprint "s1"
    And I GET "/sprints/s1/day/1"
    Then the response status is 200
    And the page contains the text "Land your first Klaviyo automation gig faster"
    And the page contains the text "Today you'll learn"
    And the page contains the text "Why this matters for your freelance career"
    And the page contains the text "What event starts the flow in this niche's tool?"
    And the page contains the text "Before you watch"

  Scenario: A legacy lesson without engagement fields still renders cleanly
    Given day 1 of sprint "s1" has a stored lesson without engagement fields
    When I GET "/sprints/s1/day/1"
    Then the response status is 200
    And the page contains the text "Klaviyo flow setup for store"
    And the page contains the text "TwoPanel"
    And the page does not contain the text "Today you'll learn"
    And the page does not contain the text "Why this matters for your freelance career"
    And the page does not contain the text "Before you watch"
    And the page does not contain the text "generation failed"

  Scenario: The pre-quiz appears before the lesson player (both variants)
    When the content generation worker runs for sprint "s1"
    And I GET "/sprints/s1/day/2"
    Then the response status is 200
    And the pre-quiz appears before the lesson player

  Scenario: The pre-quiz answer is valid (clamped, never empty)
    Given day 4 of sprint "s1" has a generated lesson with a voiceover
    When I GET "/sprints/s1/day/4"
    Then the response status is 200
    And the page contains an element with attribute "data-lesson-player"
    And the page contains the text "Before you watch"
    And the page contains the text "Checkout Started"

  Scenario: Regression — existing lesson content quality is preserved
    When the content generation worker runs for sprint "s1"
    And I GET "/sprints/s1/day/2"
    Then the response status is 200
    And the page contains the text "Common pitfalls"
    And the page contains the text "Use the exact trigger from the job posting"
    And the page contains the text "Today you'll learn"

  Scenario: Regression — the failure path still shows generation failed, never a hook
    When the content generation worker runs for sprint "s1" with no LLM
    And I GET "/sprints/s1/day/4"
    Then the response status is 200
    And the page contains the text "generation failed"
    And the page does not contain the text "Land your first Klaviyo automation gig faster"
