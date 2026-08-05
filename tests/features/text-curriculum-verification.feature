Feature: Text-Based Curriculum Content Curation
  As a user
  I want the platform to generate rich text-based lesson content using the learning science algorithm
  So that I can learn effectively without relying on video content

  Background:
    Given the curriculum generator API is available
    And I am logged in and enrolled in "Web Scraping with Python"

  #  CORE CONTENT STRUCTURE # # # # # # # # # # ─

  Scenario: TC1 — Each day has 6 text sections (Hook, Concept, Practice, Retrieval, Spaced Review, Preview)
    When a 30-day curriculum is generated for "Web Scraping with Python"
    Then each day in the database should contain:
      | Field | Purpose |
      | hook | 2-3 sentence hook connecting to learner's goal |
      | concept | 3-5 paragraph concept explanation with real examples |
      | practice_task | 3-5 step hands-on exercise producing tangible output |
      | retrieval | 3 reflection prompts requiring writing (not multiple choice) |
      | spaced_review | 2-3 sentence connection to prior learning |
      | preview | 1 sentence teasing next lesson |
    And each field should be a non-empty string with at least 50 characters

  Scenario: TC2 — Hook section is engaging and goal-oriented
    When I read the hook for any day
    Then it should start with a connection to landing a client
# OR include a surprising fact or statistic
# OR end with a driving question
    And it should be 2-5 sentences long
    And it should NOT contain generic filler like "In today's lesson"

  Scenario: TC3 — Concept section teaches ONE concept
    When I read the concept section for any day
    Then it should focus on exactly ONE core concept
    And include a real freelancing example
    And include a metaphor or analogy
    And answer "why does this matter for getting clients?"
    And be 3-5 paragraphs with 3-4 sentences each

  Scenario: TC4 — Practice section is hands-on with tangible output
    When I read the practice section
    Then it should have 3-5 actionable steps
    And produce a tangible output (code, proposal, portfolio piece, etc.)
    And include a template or framework reference
    And be slightly challenging but achievable in 20-25 minutes

  Scenario: TC5 — Retrieval section requires writing, not selecting
    When I read the retrieval section
    Then it should contain EXACTLY 3 reflection prompts
    And prompt 1 should ask: "Write down the 3 most important things you learned today"
    And prompt 2 should ask: "Explain the core concept to someone who knows nothing about it"
    And prompt 3 should ask: "What's one thing you're still confused about?"
    And none of the prompts should be multiple choice or yes/no questions

  Scenario: TC6 — Spaced review connects to prior learning
    When I read the spaced review section
    Then it should reference a concept from a previous day
    AND include a specific application question
    And be 2-4 sentences long

  #  CONTENT QUALITY # # # # # # # # # # # # ──

  Scenario: TQ1 — No generic fallback content
    When I scan all 30 days in the database
    Then no day title should contain "Part" (e.g., "Part 1", "Part 2")
    And no practice_task should contain "Hands-on exercise related to today's"
    And no description should contain "Learn key concepts"
    And at least 20 unique practice tasks should exist across 30 days

  Scenario: TQ2 — Content is readable at 8th grade level
    When I analyze any day's concept section
    Then sentences should average 15-20 words
    And paragraphs should be 3-4 sentences max
    And technical terms should be explained on first use

  Scenario: TQ3 — Each day builds on previous days
    When I examine the progression from Day 1 to Day 30
    Then Day 1-7 should cover foundation concepts
    And Day 8-15 should cover intermediate skills
    And Day 16-23 should cover application/portfolio work
    And Day 24-30 should cover mastery/income generation
    And later days should reference concepts introduced in earlier days

  #  DATABASE PERSISTENCE # # # # # # # # # # # 

  Scenario: TQ4 — All 30 days saved with complete data
    Given curriculum has been generated for "Web Scraping with Python"
    When I query the curriculum_days table
    Then I should find exactly 30 rows
    And each row should have:
      | Column | Requirement |
      | title | non-empty, at least 10 chars |
      | description | non-empty, at least 100 chars (contains concept) |
      | learning_objectives | non-empty, at least 50 chars (contains hook) |
      | practice_task | non-empty, at least 100 chars |
      | apply_task | non-empty, at least 50 chars |
      | video_title | non-empty |

  Scenario: TQ5 — Cohorts have videos for all days
    Given curriculum has been generated
    When I query the cohort_videos table
    Then I should find exactly 30 video records for this cohort
    And each should have a day_number from 1 to 30
    And each should have production_status "ready"

  #  TEXT RENDERING # # # # # # # # # # # # # ─

  Scenario: TR1 — Day detail page shows all text sections
    When I visit /dashboard/day/5
    Then I should see the hook/concept content (description field)
    And I should see the practice task
    And I should see the apply/spaced review content
    And I should see "Day 5" in the page title
    And all text should be readable (no raw JSON, no escape characters)

  Scenario: TR2 — Curriculum list shows preview text
    When I view the curriculum on the topic detail page
    Then each day row should show:
      | Element | Visible |
      | Day number | Yes |
      | Title | Yes |
      | Practice task preview | Yes (first 60 chars) |
    And each row should be a clickable link to /dashboard/day/<n>
