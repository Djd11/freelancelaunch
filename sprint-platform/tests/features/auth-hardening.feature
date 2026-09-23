Feature: Auth hardening (UAT BUG-1/2/3)
  As a platform owner pre-launch
  I want login to verify credentials and the auth surface to behave predictably
  So that nobody can sign in as another user just by knowing their email

  Background:
    Given the app is running against the live test database

  # BUG-1: password must actually be validated (was: email-only login)
  Scenario: Wrong password is rejected
    When I sign in with email "demo@sprint-platform.local" and password "totally-wrong-pass"
    Then the response status is 200
    And the page contains the text "Invalid email or password."
    And I do not have a session cookie authenticating me
    When I GET "/sprints"
    Then I am redirected to the login page

  Scenario: Correct password signs in
    When I sign in with email "demo@sprint-platform.local" and password "demo-password-123"
    Then the response redirects to "/sprints"
    When I GET "/sprints"
    Then the response status is 200
    And the page contains the text "Choose your sprint"

  Scenario: Missing password field is rejected
    When I sign in with email "demo@sprint-platform.local" and password ""
    Then the response status is 200
    And the page contains the text "Invalid email or password."
    And I do not have a session cookie authenticating me

  Scenario: Nonexistent email is rejected without revealing which part failed
    When I sign in with email "nobody-wrong@nonexistent.example" and password "whatever"
    Then the response status is 200
    And the page contains the text "Invalid email or password."

  # BUG-3: empty email should not masquerade as "No account found"
  Scenario: Empty email gets a clear validation message
    When I sign in with email "" and password "whatever"
    Then the response status is 200
    And the page contains the text "Enter your email address to sign in."

  # Session cookie hygiene after failed login
  Scenario: Failed login does not leak a session for the requested user
    When I sign in with email "admin@sprint-platform.local" and password "wrong"
    Then I do not have a session cookie authenticating me
    When I GET "/sprints"
    Then I am redirected to the login page

  # BUG-2: /login should not 404 for humans who type it
  Scenario: /login redirects to /auth/login
    When I GET "/login"
    Then I am redirected to the login page

  # UAT demo blocker: the password form (the only way an operator can sign in
  # the pre-created admin account) sat behind a collapsed disclosure that demo
  # audiences never find. It must be a visible sign-in option.
  Scenario: The password sign-in form is visible on the login page
    When I GET "/auth/login"
    Then the response status is 200
    And the page contains the text "Sign in with password"
    And the page does not contain the text "Use my password instead"
