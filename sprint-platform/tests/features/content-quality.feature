Feature: Day Content Quality — completable Phase A, job-grounded copy-work, Day 5 gap-fill
  As a learner who pays
  I want every Phase A copy-work day to accept my submission, Gate A to pass through
  the real day flow, and the tasks + Day 5 micro-lesson to be grounded in my cluster's
  live job postings
  So that the 14-day sprint teaches the actual work I'll get paid for — not a dead end
  or a generic template

  Background:
    Given the app is running against the live test database
    And a logged-in user
    Given I have an active sprint "s1" with 14 days for cluster "email-automation"
    And a job cluster "email-automation" with 5 active postings

  Scenario: A learner can pass Gate A through the real checkbox flow
    When I check all rubric items for project 1 of sprint "s1"
    And I submit the copy-work task for day 2 of sprint "s1" with rubric_url "https://github.com/me/p1"
    And I check all rubric items for project 2 of sprint "s1"
    And I submit the copy-work task for day 4 of sprint "s1" with rubric_url "https://github.com/me/p2"
    And I check all rubric items for project 3 of sprint "s1"
    And I submit the copy-work task for day 5 of sprint "s1" with rubric_url "https://github.com/me/p3"
    Then copy-work project 1 for sprint "s1" has submitted_url "https://github.com/me/p1"
    And copy-work project 2 for sprint "s1" has submitted_url "https://github.com/me/p2"
    And copy-work project 3 for sprint "s1" has submitted_url "https://github.com/me/p3"
    And gate "A" has passed verification for sprint "s1"
    When I GET "/sprints/s1"
    Then Phase B is not locked

  Scenario: Web-scraping lessons never inherit email-tool jargon from the prompts
    Given I have an active sprint "s3" with 14 days for cluster "web-scraping"
    And job cluster "web-scraping" has a posting titled "Scrape real-estate listings from Zillow"
    When the content generation worker runs for sprint "s3"
    Then no generation prompt for sprint "s3" mentions "Klaviyo" or "Shopify"
    And day 2 of sprint "s3" has a lesson not mentioning "Klaviyo"

  Scenario: Later-phase days draw from different postings instead of one repeated feed entry
    When the content generation worker runs for sprint "s1"
    Then days 6 to 14 draw from more than one distinct job posting

  Scenario: Seeded copy-work projects ship no placeholder source links
    When the copy-work projects are created for sprint "s1"
    Then copy-work project 1 for sprint "s1" ships no reachable source URL
    And copy-work project 2 for sprint "s1" ships no reachable source URL
    And copy-work project 3 for sprint "s1" ships no reachable source URL

  Scenario: The day view renders a generated reference build spec instead of a dead source link
    When the content generation worker runs for sprint "s1"
    And I GET "/sprints/s1/day/4"
    Then the page contains the text "Reference build"
    And the page contains the text "Screen 1:"

  Scenario: An LLM answer without a gap-fill topic never erases the flagged focus
    Given copy-work project 2 for sprint "s1" flagged gap-fill topic "mobile responsiveness"
    When the content generation worker runs for sprint "s1" and the LLM omits the gap-fill topic
    Then copy-work project 2 for sprint "s1" still has gap-fill topic "mobile responsiveness"

  Scenario: Copy-work projects are grounded in the learner's cluster job posting
    Given I have an active sprint "s2" with 14 days for cluster "web-scraping"
    And job cluster "web-scraping" has a posting titled "Scrape real-estate listings from Zillow"
    When the content generation worker runs for sprint "s2"
    Then copy-work project 1 for sprint "s2" has a title mentioning "Scrape real-estate listings"
    And copy-work project 3 for sprint "s2" has a title mentioning "Scrape real-estate listings"

  Scenario: Day 5 serves the targeted gap-fill micro-lesson on the flagged nuance
    Given copy-work project 2 for sprint "s1" flagged gap-fill topic "mobile responsiveness"
    When the content generation worker runs for sprint "s1"
    Then day 5 of sprint "s1" has a lesson mentioning "mobile responsiveness"

  Scenario: Generated lessons carry real instructional structure
    When the content generation worker runs for sprint "s1"
    Then day 2 of sprint "s1" has a lesson with at least 2 key points
    And day 2 of sprint "s1" has a lesson with a script longer than 80 characters
    And day 2 of sprint "s1" has a lesson with an objective
    And day 2 of sprint "s1" has a lesson mentioning a pitfall

  Scenario: Generated project anatomy carries a complete rubric and clone steps
    When the content generation worker runs for sprint "s1"
    Then copy-work project 1 for sprint "s1" has between 3 and 5 clone steps
    And copy-work project 1 for sprint "s1" has exactly 3 rubric items
