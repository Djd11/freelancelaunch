# App-Wide Clickable Items Audit — BDD Specification
# Every interactive element across FreelanceLaunch must work.
# Uses ONLY existing step definitions from test_page_audit.py.

Feature: App-Wide Clickable Items Audit
  As a quality gate for FreelanceLaunch
  I want every clickable element to perform its task
  So that users never hit dead links or broken buttons

  Background:
    Given the application is running at http://localhost:5000
    And the audit browser is Google Chrome (non-headless, DISPLAY=:0)


  # 1. LANDING PAGE (/) — logged out

  Scenario: LC-1 — Landing page navigation (logged out)
    Given I visit / while logged out
    Then I should see "Topics" link
    And I should see "Sign in" link
    And I should see "Get Started" link
    And I should see "Start Free" button
    And I should see "Explore Skills" button
    And the page must have zero console errors and zero failed requests


  # 2. DASHBOARD — logged in (/dashboard)

  Scenario: LC-2 — Dashboard page (logged in)
    Given I am logged in
    When I visit /dashboard
    Then I should see "Dashboard" link
    And I should see "Topics" link
    And I should see "Sprint Track" link
    And the page must have zero console errors and zero failed requests


  # 3. TOPICS EXPLORER (/topics) — logged out

  Scenario: LC-3 — Topics page (logged out)
    Given I visit /topics while logged out
    Then I should see "Web Scraping" section
    And I should see "n8n" section
    And I should see "SEO" section
    And I should see "Pandas" section
    And I should see "WordPress" section
    And the page must have zero console errors and zero failed requests


  # 4. TOPIC DETAIL PAGES (/topics/<slug>)

  Scenario: LC-4a — Topic detail: web-scraping
    Given I visit /topics/web-scraping-python while logged out
    Then I should see "Web Scraping with Python"
    And I should see "Get Started Free" link
    And the page must have zero console errors and zero failed requests

  Scenario: LC-4b — Topic detail: n8n-automation
    Given I visit /topics/n8n-automation while logged out
    Then I should see "n8n Workflow Automation"
    And the page must have zero console errors and zero failed requests

  Scenario: LC-4c — Topic detail: seo-content-writing
    Given I visit /topics/seo-content-writing while logged out
    Then I should see "SEO Content Writing"
    And the page must have zero console errors and zero failed requests

  Scenario: LC-4d — Topic detail: data-analysis-pandas
    Given I visit /topics/data-analysis-pandas while logged out
    Then I should see "Data Analysis with Pandas"
    And the page must have zero console errors and zero failed requests

  Scenario: LC-4e — Topic detail: wordpress-development
    Given I visit /topics/wordpress-development while logged out
    Then I should see "Basic WordPress Development"
    And the page must have zero console errors and zero failed requests


  # 5. DAY PAGE — tabbed content (/dashboard/day/<n>?topic=<slug>)

  Scenario: LC-5a — Day page has tabs and content
    Given I am logged in
    When I visit /dashboard/day/1?topic=web-scraping-python
    Then I should see "Overview" section
    And I should see "Practice" section
    And I should see "Apply" section
    And I should see "Introduction to Web Scraping"
    And the page must have zero console errors and zero failed requests

  Scenario: LC-5b — Day page video preview toggle
    Given I am logged in
    When I visit /dashboard/day/1?topic=web-scraping-python
    Then I should see "Play Video Preview" button
    And the page must have zero console errors and zero failed requests

  Scenario: LC-5c — Day page: back link from topic detail
    Given I am logged in
    When I visit /dashboard/day/1?topic=web-scraping-python
    Then I should see "Back to Topic" link


  # 6. PIPELINE PAGE (/freelance/pipeline)

  Scenario: LC-6 — Pipeline page (logged in)
    Given I am logged in
    When I visit /freelance/pipeline
    Then I should see "Pipeline" link
    And the page must have zero console errors and zero failed requests


  # 7. PRICING PAGE (/payments/pricing)

  Scenario: LC-7 — Pricing page (logged out)
    Given I visit /payments/pricing while logged out
    Then I should see "Pricing"
    And the page must have zero console errors and zero failed requests


  # 8. AUTH PAGES

  Scenario: LC-8a — Login page
    Given I visit /auth/login while logged out
    Then I should see email input
    And I should see password input
    And I should see a "Sign In" submit button
    And the page must have zero console errors and zero failed requests

  Scenario: LC-8b — Signup page
    Given I visit /auth/signup while logged out
    Then I should see email input
    And I should see password input
    And the page must have zero console errors and zero failed requests

  Scenario: LC-8c — Logout redirects to landing
    Given I am logged in
    When I visit /auth/logout
    Then I should be on /topics


  # 9. PLATFORM SETUP (/platforms/setup)

  Scenario: LC-9 — Platform setup page
    Given I am logged in
    When I visit /platforms/setup
    Then I should see "Platform" heading
    And the page must have zero console errors and zero failed requests


  # 10. GLOBAL NAVIGATION CONSISTENCY

  Scenario: LC-10 — Logged-in user sees consistent nav
    Given I am logged in
    When I visit each page
      | /dashboard                                    |
      | /topics                                       |
      | /topics/web-scraping-python                   |
      | /dashboard/day/1?topic=web-scraping-python    |
      | /freelance/pipeline                           |
    Then the nav bar should show:
      | Dashboard | Topics | Sprint Track |
    


  # 11. REDIRECT: logged-in user hitting / goes to /dashboard

  Scenario: LC-11 — Logged-in root redirect
    Given I am logged in
    When I visit /
    Then I should see "Dashboard"
