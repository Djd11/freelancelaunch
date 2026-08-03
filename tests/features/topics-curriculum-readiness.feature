# Topics & Curriculum Readiness — BDD Specification
# Regression suite for the 500-on-new-topic bug, curriculum day links,
# generation states, and background-job visibility.
#
# RULES:
#   1. Enrolling in ANY topic (new or existing) must NOT 500 — cohort rows
#      are linked by topics.id UUID, never by slug string.
#   2. /dashboard/day/<n> must render real lesson content whenever a
#      curriculum EXISTS for the topic — never spin forever on the
#      generation state, never 500.
#   3. When no curriculum exists, the day page shows the loading/generation
#      state (HTTP 200, "Preparing your Day"), auto-triggers generation, and
#      polls status; the user can always see what the background job is doing
#      via the live generation log.
#   4. Every clickable on topics/dashboard/day pages leads to the correct state.
#
# Test user: chinaindiatesting@gmail.com / others@2024 (dedicated test account).

Feature: Topics and Curriculum Readiness
  As a user
  I want to enroll in any topic and always reach my daily lesson
  So that a new topic never 500s and I can see what's happening in the background

  Background:
    Given the application is running at BASE_URL
    And the audit browser is Google Chrome (non-headless, DISPLAY=:0)

  # 1. TOPICS EXPLORER — browse + demand data

  Scenario: TR-1 — Topics explorer renders all curated topics as clickable cards
    Given I visit /topics while logged out
    Then the following clickables must exist and behave as specified:
      | Element                          | Type  | Intended Task                             |
      | Search input                     | Input | Typing filters topic cards live           |
      | Topic card 1 (web-scraping)      | Link  | Click → /topics/web-scraping-python       |
      | Topic card 2 (n8n)               | Link  | Click → /topics/n8n-automation            |
      | Topic card 3 (seo)               | Link  | Click → /topics/seo-content-writing       |
      | Topic card 4 (pandas)            | Link  | Click → /topics/data-analysis-pandas      |
      | Topic card 5 (wordpress)         | Link  | Click → /topics/wordpress-development     |
    And the page must have zero console errors and zero failed requests

  # 2. TOPIC DETAIL — enrolled vs logged out

  Scenario: TR-2 — Topic detail while logged out shows signup/login CTAs
    Given I am logged out
    And I visit /topics/web-scraping-python
    Then the following clickables must exist and behave as specified:
      | Element                          | Type | Intended Task                                  |
      | "Get Started Free"               | Link | Click → /auth/signup?topic=web-scraping-python |
      | "Sign in"                        | Link | Click → /auth/login?topic=web-scraping-python  |

  Scenario: TR-3 — Topic detail for an enrolled user shows dashboard CTA
    Given I am logged in
    And I visit /topics/web-scraping-python
    Then I should see "You're enrolled" banner
    And I should see "Go to Dashboard →" link to /dashboard/
    And the page must have zero console errors and zero failed requests

  # 3. ENROLLMENT — the 500 regression (slug vs UUID)

  Scenario: TR-4 — Enrolling in a fresh topic does not 500 (UUID linkage)
    Given I am logged in
    When I POST to /topics/seo-content-writing/enroll while logged in
    Then I should not receive a 500
    And my user profile should have cohort_id and selected_topic_id set
    And I should be redirected to the platform setup page

  # 4. DAY DETAIL — curriculum readiness (never stuck, never 500)

  Scenario: TR-5 — Day page renders real content when curriculum exists
    Given I am logged in
    And I visit /dashboard/day/1
    Then the page must not show the generation loading state
    And the page must not contain "Internal Server Error"
    And I should see the lesson content section
    And the following clickables must exist and behave as specified:
      | "← Back to Dashboard"            | Link     | Click → /dashboard/                          |
      | "Play Video Preview" button      | Button   | Presence: inline preview toggles (no 500)    |
      | Progress checkboxes (3)          | Checkbox | Present on the page                          |

  Scenario: TR-6 — Day page for an ungenerated topic shows loading state, not 500
    Given I am logged in
    And I visit /dashboard/day/2 with a topic that has no curriculum
    Then I should get a 200 response
    And I should see "Preparing your Day"
    And the page must not contain "Internal Server Error"

  Scenario: TR-7 — Generation status endpoint answers for any slug
    Given I am logged in
    When I query the generation status for web-scraping-python
    Then the response should be valid JSON with a status field

  Scenario: TR-8 — Generation log endpoint shows what the background job is doing
    Given I am logged in
    When I query the generation log for web-scraping-python
    Then the response should be valid JSON
    And the response should contain a log_entries field

  # 5. GENERATION API — auth + enrollment guards

  Scenario: TR-9 — Generation API rejects unauthenticated requests
    Given I am logged out
    When I POST to /api/generate-curriculum/web-scraping-python without logging in
    Then I should receive a 401 response

  # 6. ROUTING SAFETY

  Scenario: TR-10 — Unknown topic slug redirects cleanly (no 500)
    When I visit /topics/definitely-not-a-real-topic
    Then I should be redirected to /topics

  # CRUD COVERAGE
  # Table                          Create  Read  Update  Delete
  # cohorts (via enroll)           TR-4    TR-4  —       —
  # user_profiles (cohort assign)  TR-4    TR-4  TR-4    —
  # curriculum_days (read)         —       TR-5  —       —
  # curriculum_generation_log      —       TR-8  —       —
