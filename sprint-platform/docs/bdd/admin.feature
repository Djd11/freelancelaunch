Feature: Admin Dashboard & Feed Curation
  As a platform administrator
  I want to curate the job feed and create cohorts
  So that sprinters have fresh, demand-validated opportunities

  Background:
    Given the app is running against the live test database
    And I am logged in as an admin user

  Scenario: Admin can access the admin dashboard
    When I GET "/admin/"
    Then the response status is 200
    And the page contains the text "Admin Dashboard"

  Scenario: Admin can view job clusters
    When I GET "/admin/clusters"
    Then the response status is 200
    And the page contains the text "Job Clusters"

  Scenario: Admin can create a new job cluster
    When I POST to "/admin/clusters/create" with JSON {"cluster_key": "test-cluster", "display_name": "Test Cluster", "icon": "🧪", "description": "A test cluster", "job_count": 100, "avg_rate": 50, "growth_score": 10, "status": "active"}
    Then the response status is 201
    And the JSON has field "cluster_key" equal to "test-cluster"

  Scenario: Admin can view job feed postings
    When I GET "/admin/feed"
    Then the response status is 200
    And the page contains the text "Job Feed"

  Scenario: Admin can add a job posting to the feed
    When I POST to "/admin/feed/create" with JSON {"cluster_key": "email-automation", "title": "New Klaviyo Flow", "source": "curated", "source_url": "https://example.com/job", "description": "Build a new flow", "skills": ["klaviyo", "email"], "rate": 200, "experience_needed": "intermediate", "unlock_day": 5, "status": "active"}
    Then the response status is 201
    And the JSON has field "title" equal to "New Klaviyo Flow"

  Scenario: Admin can create a cohort
    When I POST to "/admin/cohorts/create" with JSON {"cluster_key": "email-automation", "name": "Cohort #13", "start_date": "2026-09-01", "end_date": "2026-09-14", "status": "upcoming"}
    Then the response status is 201
    And the JSON has field "name" equal to "Cohort #13"

  Scenario: Admin can view all cohorts
    When I GET "/admin/cohorts"
    Then the response status is 200
    And the page contains the text "Cohorts"

  Scenario: Non-admin user cannot access admin dashboard
    Given I am not logged in
    When I GET "/admin/"
    Then the response status is 302
    And the response redirects to "/auth/login"

  Scenario: Regular logged-in user cannot access admin dashboard
    Given a logged-in user
    When I GET "/admin/"
    Then the response status is 403

  Scenario: Admin-curated cluster appears on the learner's sprint picker
    When I POST to "/admin/clusters/create" with JSON {"cluster_key": "handoff-cluster", "display_name": "Handoff Cluster", "icon": "🤝", "description": "Curated by admin for learners", "job_count": 120, "avg_rate": 55, "growth_score": 9, "status": "active"}
    Then the response status is 201
    Given a logged-in user
    When I GET "/sprints"
    Then the response status is 200
    And the page contains the text "Handoff Cluster"

  # CRUD COVERAGE (Live Supabase)
  # Table                 Create  Read  Update  Delete
  # ─────────────────────────────────────────────────────
  # job_clusters           C1      R1    —       —
  # job_feed               C2      R2    —       —
  # cohorts                C3      R3    —       —