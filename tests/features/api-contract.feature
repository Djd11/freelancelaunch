Feature: HTTP API Contract
  As a client of the FreelanceLaunch web app
  I want the JSON APIs to follow a stable contract
  So that the frontend and integrations can rely on status codes and shapes

  Background:
    Given the app is running with an in-memory test database
    And a test user is logged in

  # ─────────────────────────────────────────────────────────────────────
  # 1. AUTH GATING — every JSON API returns 401 when anonymous
  # ─────────────────────────────────────────────────────────────────────
  Scenario: Anonymous callers are rejected with 401 on state-changing APIs
    Given I am not logged in
    When I POST to "/api/progress/mark" with JSON {}
    Then the response status is 401
    And the JSON has error "Not logged in"

  Scenario: Anonymous callers get 401 from platform APIs
    Given I am not logged in
    When I POST to "/platforms/api/verify" with JSON {"platform": "upwork"}
    Then the response status is 401
    And the JSON has error "Not logged in"

  # ─────────────────────────────────────────────────────────────────────
  # 2. HEALTH — liveness contract
  # ─────────────────────────────────────────────────────────────────────
  Scenario: Health endpoint reports status ok
    When I GET "/health"
    Then the response status is 200
    And the JSON has field "status" equal to "ok"

  # ─────────────────────────────────────────────────────────────────────
  # 3. PROGRESS — /api/progress/mark + /rate
  # ─────────────────────────────────────────────────────────────────────
  Scenario: Progress mark rejects an unknown field with 400
    When I POST to "/api/progress/mark" with JSON
      """
      {"cohort_video_id": "cv1", "field": "bogus"}
      """
    Then the response status is 400

  Scenario: Progress mark records a completed section
    Given a cohort video "cv1" exists
    When I POST to "/api/progress/mark" with JSON
      """
      {"cohort_video_id": "cv1", "field": "video_watched", "day_number": 1}
      """
    Then the response status is 200
    And the JSON has field "success" equal to true

  Scenario: Progress rate rejects an out-of-range rating with 400
    When I POST to "/api/progress/rate" with JSON
      """
      {"cohort_video_id": "cv1", "rating": 9}
      """
    Then the response status is 400

  Scenario: Progress rate records a 1-5 self-rating
    Given a cohort video "cv1" exists
    When I POST to "/api/progress/rate" with JSON
      """
      {"cohort_video_id": "cv1", "rating": 4}
      """
    Then the response status is 200

  # ─────────────────────────────────────────────────────────────────────
  # 4. ENROLL — /enroll/new
  # ─────────────────────────────────────────────────────────────────────
  Scenario: Enroll rejects a topic shorter than 3 chars
    When I POST to "/enroll/new" with JSON {"topic": "ab"}
    Then the response status is 400
    And the JSON has error "Topic name must be at least 3 characters"

  Scenario: Enroll creates a sprint and redirects to platform setup
    When I POST to "/enroll/new" with JSON {"topic": "Email Automation"}
    Then the response status is 200
    And the JSON has field "status" equal to "enrolled"
    And the JSON has field "redirect" equal to "/platforms/setup"

  # ─────────────────────────────────────────────────────────────────────
  # 5. PLATFORMS — /platforms/api/*
  # ─────────────────────────────────────────────────────────────────────
  Scenario: Platform select rejects an unknown platform with 400
    When I POST to "/platforms/api/select" with JSON {"platform": "linkedin"}
    Then the response status is 400
    And the JSON has error "Invalid platform: linkedin"

  Scenario: Platform select creates a pending link
    When I POST to "/platforms/api/select" with JSON {"platform": "upwork"}
    Then the response status is 200
    And the JSON has field "status" equal to "created"
    And the JSON has field "signup_url" matching "^https"

  Scenario: Platform verify marks the link verified
    Given the platform "upwork" is linked with status "pending"
    When I POST to "/platforms/api/verify" with JSON {"platform": "upwork"}
    Then the response status is 200
    And the JSON has field "status" equal to "verified"

  Scenario: Platform status reports has_verified after a verification
    Given the platform "upwork" is linked with status "verified"
    When I GET "/platforms/api/status"
    Then the response status is 200
    And the JSON has field "has_verified" equal to true

  # ─────────────────────────────────────────────────────────────────────
  # 6. FREELANCE — /freelance/api/update
  # ─────────────────────────────────────────────────────────────────────
  Scenario: Pipeline update rejects an unknown field with 400
    When I POST to "/freelance/api/update" with JSON
      """
      {"field": "not_a_field", "value": 1}
      """
    Then the response status is 400
    And the JSON has error "Invalid field: not_a_field"

  Scenario: Pipeline update accepts a known stage value
    Given a freelance pipeline row exists for the user
    When I POST to "/freelance/api/update" with JSON
      """
      {"field": "stage", "value": "applying"}
      """
    Then the response status is 200
    And the JSON has field "success" equal to true

  # ─────────────────────────────────────────────────────────────────────
  # 7. SEARCH — /search/api + /search/suggestions
  # ─────────────────────────────────────────────────────────────────────
  Scenario: Search rejects a short query
    When I GET "/search/api?q=a"
    Then the response status is 200
    And the JSON has error "Query too short"

  Scenario: Search returns a stable platform result shape for a known topic
    When I GET "/search/api?q=email%20automation"
    Then the response status is 200
    And the JSON has field "curated_count" equal to 0
    And the JSON has field "platform_results" as an object

  Scenario: Suggestions returns an array of topic objects
    When I GET "/search/suggestions"
    Then the response status is 200
    And the response body is a JSON array

  # ─────────────────────────────────────────────────────────────────────
  # 8. SPRINT TRACK — /sprints/*
  # ─────────────────────────────────────────────────────────────────────
  Scenario: Completing a sprint day returns the updated meter JSON
    Given an active sprint "s1" on day 1 for the test user
    And a job cluster "email-automation" with 450 active postings
    When I POST to "/sprints/s1/day/1/complete"
    Then the response status is 200
    And the JSON has field "ok" equal to true
    And the JSON has field "next_day" equal to 2
    And the JSON path "meter.unlocked" is an integer

  Scenario: A sprint dashboard redirects anonymous users to login
    Given I am not logged in
    When I GET "/sprints/s1"
    Then the response status is 302
