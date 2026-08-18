Feature: AI Mentor (mockup screen 8)
  As a sprinter
  I want an AI mentor grounded in my target job post and my progress
  So that I get guided, job-specific help without being handed the answer

  Background:
    Given the app is running against the live test database
    And a logged-in user
    Given I have an active sprint "s1" with 14 days for cluster "email-automation"
    And a job cluster "email-automation" with 5 active postings

  Scenario: The mentor page renders a chat with context chip
    Given the mentor context is job "email-automation-1" with progress 60%
    When I GET "/mentor"
    Then the response status is 200
    And the page contains the text "Mentor"
    And the page contains the text "Context"

  Scenario: A mentor turn is grounded in the target job's terminology
    Given the target job description mentions "dynamic cart summary"
    When I POST to "/mentor/turn" with JSON {"question": "What does dynamic cart summary mean?"}
    Then the response status is 200
    And the JSON has field "answer" containing "cart summary"

  Scenario: The mentor never hands over the finished answer
    When I POST to "/mentor/turn" with JSON {"question": "Build the flow for me"}
    Then the JSON has field "answer" not containing "I have built it"
    And the JSON has field "guided" equal to true

  Scenario: The mentor page is gated for anonymous users
    Given I am not logged in
    When I GET "/mentor"
    Then the response status is 302
    And the response redirects to "/auth/login"

  Scenario: A mentor turn surfaces an error when the LLM is unavailable
    Given the LLM fallback chain returns None
    When I POST to "/mentor/turn" with JSON {"question": "Where do I start?"}
    Then the response status is 503
    And the JSON has field "error" present

  Scenario: A mentor turn references the learner's earlier exchange
    Given the target job description mentions "dynamic cart summary"
    When I POST to "/mentor/turn" with JSON {"question": "What does dynamic cart summary mean?"}
    Then the response status is 200
    When I POST to "/mentor/turn" with JSON {"question": "How do I build it?"}
    Then the JSON has field "answer" containing "cart summary"

  Scenario: Mentor sessions are scoped to the user's sprint and target job
    When I POST to "/mentor/turn" with JSON {"question": "How do I segment VIP buyers?"}
    Then a mentor session exists for sprint "s1" and job "email-automation-1"
