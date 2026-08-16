Feature: API Surface & Negative Paths (eng-spec §6, arch §7)
  As an operator or API consumer
  I want the JSON endpoints to answer correctly and refuse bad input without 500s
  So that the platform is robust, ownership-gated, and never crashes on bad requests

  Background:
    Given the app is running against the live test database
    And a logged-in user
    Given I have an active sprint "s1" with 14 days for cluster "email-automation"
    And a job cluster "email-automation" with 5 active postings

  Scenario: The health endpoint reports live Supabase reachability
    When I GET "/health"
    Then the response status is 200
    And the JSON has field "status" equal to "ok"
    And the JSON has field "mode" equal to "supabase"
    And the JSON has field "clusters_reachable" equal to true

  Scenario: An unknown route is a 404, never a 500
    When I GET "/no-such-page"
    Then the response status is 404

  Scenario: Auth-gated API endpoints refuse anonymous users
    Given I am not logged in
    When I GET "/sprints/s1/generation"
    Then the response status is 302
    And the response redirects to "/auth/login"

  Scenario: Enrollment is POST-only — a GET must never have side effects
    When I GET "/sprints/email-automation/start"
    Then the response status is 405

  Scenario: Enrollment refuses anonymous users
    Given I am not logged in
    When I POST to "/sprints/email-automation/start"
    Then the response status is 302
    And the response redirects to "/auth/login"

  Scenario: Another user's sprint data is never served
    Given an active sprint "other-sprint" for another user
    When I GET "/sprints/other-sprint/generation"
    Then the response status is 404
    And the JSON has field "error" equal to "not found"

  Scenario: Writing to another user's sprint is refused
    Given an active sprint "other-sprint" for another user
    When I POST to "/sprints/other-sprint/day/4/complete"
    Then the response status is 404
    And the JSON has field "ok" equal to false

  Scenario: Malformed sprint ids short-circuit instead of crashing
    When I GET "/sprints/not-a-uuid/day/4"
    Then the response status is 302
    And the response redirects to "/dashboard/"

  Scenario: Completing a non-existent day is refused, never 500
    When I POST to "/sprints/s1/day/99/complete"
    Then the response status is 404
    And the JSON has field "ok" equal to false

  Scenario: A day view for a missing day redirects, never 500
    When I GET "/sprints/s1/day/99"
    Then the response status is 302
    And the response redirects to the sprint dashboard

  Scenario: The mentor turn endpoint refuses anonymous users
    Given I am not logged in
    When I POST to "/mentor/turn" with JSON {"question": "Where do I start?"}
    Then the response status is 302
    And the response redirects to "/auth/login"

  Scenario: An empty mentor question degrades gracefully
    When I POST to "/mentor/turn" with JSON {"question": ""}
    Then the response status is 200
    And the JSON has field "guided" equal to true

  Scenario: Demand refresh is an explicit admin action — regular users get 403
    When I POST to "/admin/clusters/email-automation/refresh"
    Then the response status is 403
    And the JSON has field "error" containing "Admin"

  Scenario: Demand refresh recomputes counters and writes a snapshot
    # Scoped to its own cluster so refresh never mutates the shared static
    # feed/counters — the cluster + feed rows are tracked and cascade-clean.
    Given I am logged in as an admin user
    When I POST to "/admin/clusters/create" with JSON {"cluster_key": "refresh-cluster", "display_name": "Refresh Cluster", "icon": "📡", "description": "Scoped test cluster", "job_count": 0, "avg_rate": 0, "growth_score": 0, "status": "active"}
    And I POST to "/admin/feed/create" with JSON {"cluster_key": "refresh-cluster", "title": "Refresh job one", "source": "curated", "source_url": "https://example.com/job", "description": "A job", "skills": ["email"], "rate": 100, "experience_needed": "intermediate", "unlock_day": 1, "status": "active"}
    When I POST to "/admin/clusters/refresh-cluster/refresh" with JSON {}
    Then the response status is 200
    And the JSON has field "cluster_key" equal to "refresh-cluster"
    And the JSON path "job_count" is an integer

  Scenario: Login refuses emails with no account
    When I POST the login form with email "nobody@sprint-platform.local"
    Then the response status is 200
    And the page contains the text "No account found"

  Scenario: The dashboard landing redirects to the sprint picker
    When I GET "/dashboard/"
    Then the response status is 302
    And the response redirects to "/sprints"
