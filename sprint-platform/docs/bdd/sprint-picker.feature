Feature: Sprint Picker (mockup screen 2)
  As a learner
  I want to choose a demand-validated sprint from live job-cluster cards
  So that I train against skills with real market demand

  Background:
    Given the app is running with an in-memory test database
    And a job cluster "email-automation" with job_count 450 and avg_rate 62 and growth_score 18
    And a job cluster "web-scraping" with job_count 322 and avg_rate 48 and growth_score 12
    And a job cluster "ai-chatbots" with job_count 268 and avg_rate 55 and growth_score 15

  Scenario: The picker lists all active sprint cards
    When I GET "/sprints"
    Then the response status is 200
    And the page contains the text "Email Automation"
    And the page contains the text "Web Scraping"
    And the page contains the text "AI Chatbots"

  Scenario: A sprint card shows live demand badges, not stale numbers
    When I GET "/sprints"
    Then the page contains the text "450 jobs open"
    And the page contains the text "322 jobs open"
    And the page contains the text "$62/hr"
    And the page contains the text "14 days"

  Scenario: A sprint card offers a Start CTA
    When I GET "/sprints"
    Then the page contains a link to start a sprint for "email-automation"

  Scenario: Request a sprint is available for unlisted skills
    When I GET "/sprints"
    Then the page contains the text "Request a sprint"

  Scenario: Requesting a sprint records a requested cluster
    When I submit a request-a-sprint form for skill "notion-automation"
    Then a job cluster "notion-automation" is recorded as requested

  Scenario: The picker is gated for anonymous users
    Given I am not logged in
    When I GET "/sprints"
    Then the response status is 302
    And the response redirects to "/auth/login"
