# Topic-Scoped Days & Previews — BDD Specification
# Regression suite for the reported bug: "all topics point to Shopify Dropshipping".
#
# RULES:
#   1. Browsing /topics/<slug> and clicking a day link must show THAT topic's
#      lesson — never the user's cohort topic's lesson.
#   2. /dashboard/day/<n>?topic=<slug> resolves content from <slug>'s own
#      curriculum (cohort-agnostic).
#   3. Progress checkboxes appear ONLY when the user's cohort topic matches
#      the viewed topic (cohort mismatch → read-only lesson).
#   4. A not-ready preview's "Back to Day N" link must preserve the ?topic=
#      scope — clicking it must NOT fall back to the cohort's topic.
#   5. The cohort-scoped preview (no ?topic=) must NOT leak a topic param.
#
# Test user: chinaindiatesting@gmail.com / others@2024 (dedicated test account).
# This user's cohort is Shopify Dropshipping — the canonical "wrong topic".

Feature: Topic-Scoped Days and Previews
  As a user browsing any topic
  I want day lessons and previews to stay on that topic
  So that I never see another topic's (e.g. Shopify's) content

  Background:
    Given the application is running at BASE_URL
    And the audit browser is Google Chrome (non-headless, DISPLAY=:0)
    And I am logged in

  Scenario: TS-1 — Day links from a topic page are topic-scoped
    When I visit /topics/n8n-automation
    Then each day should be a clickable link to /dashboard/day/<n>
    And every day link should carry ?topic=n8n-automation

  Scenario: TS-2 — Topic-scoped day renders that topic's lesson, not the cohort's
    When I visit /dashboard/day/1?topic=n8n-automation
    Then I should see "n8n Workflow Automation"
    And the page must not contain "Shopify"

  Scenario: TS-3 — Topic-scoped day for web-scraping shows web-scraping content
    When I visit /dashboard/day/1?topic=web-scraping-python
    Then I should see "Introduction to Web Scraping"
    And the page must not contain "Shopify"

  Scenario: TS-4 — Cohort mismatch hides progress checkboxes (read-only lesson)
    When I visit /dashboard/day/1?topic=n8n-automation
    Then I should see the lesson content section
    And the page must not show progress checkboxes

  Scenario: TS-5 — Not-ready preview back link keeps the topic scope
    When I open the preview for day 99 of web-scraping-python
    Then the preview should show "Preview not ready yet"
    And the preview back link should point to /dashboard/day/99?topic=web-scraping-python

  Scenario: TS-6 — Clicking the not-ready back link stays on the topic
    When I open the preview for day 99 of web-scraping-python
    And I click the preview back link
    Then I should be on /dashboard/day/99?topic=web-scraping-python
    And the page must not contain "Shopify"

  Scenario: TS-7 — Cohort-scoped not-ready preview leaks no topic param
    When I open the cohort preview for day 99
    Then the preview should show "Preview not ready yet"
    And the preview back link should point to /dashboard/day/99
