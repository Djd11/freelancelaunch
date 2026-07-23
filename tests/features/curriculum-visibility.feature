Feature: Curriculum Visibility After Enrollment
  As an enrolled user or admin
  I want to see the full curriculum instead of a placeholder message
  So that I can start learning immediately

  Background:
    Given the application is running at https://freelancelaunch.onrender.com

  Scenario: E1 — Enrolled user sees curriculum, not placeholder
    Given I am logged in as an enrolled user
    When I view the topic detail page for my enrolled topic
    Then I should NOT see "Full curriculum unlocks when you enroll"
    And I should see the full 30-day curriculum with actual day titles
    And each day should show a title, description, practice task, and apply task

  Scenario: E2 — Unenrolled user sees placeholder message
    Given I am logged in but NOT enrolled in this topic
    When I view the topic detail page
    Then I should see "Full curriculum unlocks when you enroll"
    And I should see a preview of 10 days only (not 30)

  Scenario: E3 — Logged out user sees enroll prompt
    Given I am logged out
    When I view the topic detail page
    Then I should see "Get Started Free" button
    And I should see a preview of 10 days
    And I should see "Full curriculum unlocks when you enroll"

  Scenario: E4 — Admin sees full curriculum regardless of enrollment
    Given I am logged in as admin
    When I view any topic detail page
    Then I should see the full 30-day curriculum
    And I should NOT see "Full curriculum unlocks when you enroll"
    And I should see admin-specific labels or additional detail

  Scenario: E5 — Multiple enrolled days shown correctly
    Given I am enrolled and have completed Day 5
    When I view the topic detail page
    Then Days 1-5 should show a "completed" indicator
    And Day 6 should be highlighted as "next up"
    And Days 7-30 should show as "upcoming"

  Scenario: E6 — Curriculum from DB shows actual content
    Given the topic has a curriculum stored in the database
    When I view the topic detail page as an enrolled user
    Then each day should display its actual title, description, practice_task, and apply_task from the database
    And the days should not be hardcoded placeholder text
