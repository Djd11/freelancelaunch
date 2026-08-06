# Content Isolation — BDD Specification
# Each topic's curriculum must be unique and never leak into another topic.
# Uses ONLY existing step definitions from test_page_audit.py.

Feature: Content Isolation Across Topics
  As a learner studying multiple topics
  I want each topic's curriculum to be unique and self-contained
  So that I never see cross-contamination between different subjects

  Background:
    Given the application is running at http://localhost:5000
    And the audit browser is Google Chrome (non-headless, DISPLAY=:0)
    And I am logged in


  # ═══════════════════════════════════════════════════════════════════
  # 1. CURRICULUM CONTENT — TOPIC-SPECIFIC KEYWORDS
  # ═══════════════════════════════════════════════════════════════════

  Scenario: CI-1a — Day 1 of web-scraping has web-scraping content
    When I visit /dashboard/day/1?topic=web-scraping-python
    Then I should see "Introduction to Web Scraping"
    And I should NOT see "Shopify"
    And I should NOT see "n8n"
    And I should NOT see "pandas"
    And the page must have zero console errors and zero failed requests

  Scenario: CI-1b — Day 1 of n8n-automation has n8n content
    When I visit /dashboard/day/1?topic=n8n-automation
    Then I should NOT see "Shopify"
    And I should NOT see "web scraping"
    And I should NOT see "pandas"
    And I should NOT see "WordPress"
    And the page must have zero console errors and zero failed requests

  Scenario: CI-1c — Day 1 of seo-content-writing has SEO content
    When I visit /dashboard/day/1?topic=seo-content-writing
    Then I should NOT see "Shopify"
    And I should NOT see "web scraping"
    And I should NOT see "n8n"
    And I should NOT see "pandas"
    And the page must have zero console errors and zero failed requests

  Scenario: CI-1d — Day 1 of data-analysis-pandas has pandas content
    When I visit /dashboard/day/1?topic=data-analysis-pandas
    Then I should NOT see "Shopify"
    And I should NOT see "web scraping"
    And I should NOT see "n8n"
    And I should NOT see "SEO"
    And the page must have zero console errors and zero failed requests

  Scenario: CI-1e — Day 1 of wordpress-development has WordPress content
    When I visit /dashboard/day/1?topic=wordpress-development
    Then I should NOT see "Shopify"
    And I should NOT see "web scraping"
    And I should NOT see "n8n"
    And I should NOT see "pandas"
    And the page must have zero console errors and zero failed requests


  # ═══════════════════════════════════════════════════════════════════
  # 2. CROSS-TOPIC CONTAMINATION — NEGATIVE CHECKS
  # ═══════════════════════════════════════════════════════════════════

  Scenario: CI-2a — Web scraping must not show other topic content
    When I visit /dashboard/day/1?topic=web-scraping-python
    Then I should NOT see "Shopify Dropshipping"
    And I should NOT see "n8n Workflow Automation"
    And I should NOT see "WordPress Development"
    And I should NOT see "SEO Content Writing"
    And I should NOT see "Data Analysis with Pandas"

  Scenario: CI-2b — n8n must not show scraping content
    When I visit /dashboard/day/1?topic=n8n-automation
    Then I should NOT see "Shopify Dropshipping"
    And I should NOT see "Web Scraping with Python"
    And I should NOT see "BeautifulSoup"
    And I should NOT see "pandas.DataFrame"

  Scenario: CI-2c — SEO must not show other topic content
    When I visit /dashboard/day/1?topic=seo-content-writing
    Then I should NOT see "Shopify Dropshipping"
    And I should NOT see "BeautifulSoup"
    And I should NOT see "n8n"
    And I should NOT see "pandas"


  # ═══════════════════════════════════════════════════════════════════
  # 3. DIFFERENT DAYS WITHIN A TOPIC — CONTENT VARIES
  # ═══════════════════════════════════════════════════════════════════

  Scenario: CI-3a — Day 1 and Day 2 of web-scraping differ
    When I visit /dashboard/day/1?topic=web-scraping-python
    Then I should see "Introduction to Web Scraping"
    When I visit /dashboard/day/2?topic=web-scraping-python
    Then I should NOT see "Introduction to Web Scraping"
    And the page must have zero console errors and zero failed requests

  Scenario: CI-3b — Day 1 and Day 2 of n8n differ
    When I visit /dashboard/day/1?topic=n8n-automation
    When I visit /dashboard/day/2?topic=n8n-automation
    Then the page must have zero console errors and zero failed requests


  # ═══════════════════════════════════════════════════════════════════
  # 4. SAME DAY NUMBER ACROSS TOPICS — DIFFERENT TITLES
  # ═══════════════════════════════════════════════════════════════════

  Scenario: CI-4a — Day 1 of web-scraping and Day 1 of n8n are different
    When I visit /dashboard/day/1?topic=web-scraping-python
    Then I should see "Introduction to Web Scraping"
    When I visit /dashboard/day/1?topic=n8n-automation
    Then I should NOT see "Introduction to Web Scraping"


  # ═══════════════════════════════════════════════════════════════════
  # 5. PREVIEW TEXT MATCHES CURRICULUM
  # ═══════════════════════════════════════════════════════════════════

  Scenario: CI-5a — Web scraping preview shows scraping title
    When I open the preview for day 1 of web-scraping-python directly
    Then the preview should show "Web Scraping"
    And the preview should not show "n8n"

  Scenario: CI-5b — n8n preview shows n8n title
    When I open the preview for day 1 of n8n-automation directly
    Then the preview should show "n8n"
    And the preview should not show "Web Scraping"


  # ═══════════════════════════════════════════════════════════════════
  # 6. TOPIC DETAIL PAGES — SELF-CONTAINED
  # ═══════════════════════════════════════════════════════════════════

  Scenario: CI-6a — Web scraping topic detail is self-contained
    When I visit /topics/web-scraping-python
    Then I should see "Web Scraping with Python"
    And I should NOT see "n8n"
    And I should NOT see "WordPress"
    And I should NOT see "pandas"
    And I should NOT see "Shopify"

  Scenario: CI-6b — n8n topic detail is self-contained
    When I visit /topics/n8n-automation
    Then I should see "n8n Workflow Automation"
    And I should NOT see "web scraping"
    And I should NOT see "BeautifulSoup"
    And I should NOT see "Shopify"


  # ═══════════════════════════════════════════════════════════════════
  # 7. DAY LINKS FROM TOPIC PAGE — CORRECT TOPIC SCOPE
  # ═══════════════════════════════════════════════════════════════════

  Scenario: CI-7a — Day links from web-scraping carry correct slug
    When I visit /topics/web-scraping-python
    Then every day link should carry ?topic=web-scraping-python

  Scenario: CI-7b — Day links from n8n carry correct slug
    When I visit /topics/n8n-automation
    Then every day link should carry ?topic=n8n-automation

  Scenario: CI-7c — Day links from SEO carry correct slug
    When I visit /topics/seo-content-writing
    Then every day link should carry ?topic=seo-content-writing
