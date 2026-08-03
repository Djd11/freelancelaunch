# Clickable Items Audit — BDD Specification
# Every clickable element on every page must do its intended task.
# The automated runner enumerates ALL interactive elements (a[href], button,
# input[type=submit|checkbox|radio], select, summary, [role=button], [onclick],
# [hx-post]) and verifies each against the tables below.
#
# RULES OF THE AUDIT:
#   1. Any clickable element found on a page but NOT listed in that page's table
#      => FAIL "undocumented clickable element"
#   2. Any element listed in a table but NOT found on the page => FAIL "missing"
#   3. Links: click => must navigate to the stated destination (HTTP 200)
#   4. External links: must carry the stated href + target=_blank (not navigated)
#   5. Buttons/forms: submitted only when the side-effect is on the TEST user
#      (progress, pipeline, contracts, deliverables, platforms). Buttons whose
#      side-effect is external (Stripe checkout, video render, LLM generation,
#      signup of a NEW user) are verified for presence/wiring only and reported
#      as SKIPPED with reason.
#   6. Every page must render with ZERO console errors and ZERO failed requests.
#
# Test user: chinaindiatesting@gmail.com / others@2024 (dedicated test account).

Feature: Clickable Items Audit
  As a quality gate for FreelanceLaunch
  I want every clickable element to perform its intended task
  So that users never hit a dead button, broken link, or silent failure

  Background:
    Given the application is running at BASE_URL
    And the audit browser is Google Chrome (non-headless, DISPLAY=:0)


  # 1. LANDING PAGE (/) — logged out

  Scenario: LAND-1 — Every clickable on the landing page performs its task
    Given I visit / while logged out
    Then the following clickables must exist and behave as specified:
      | Element                          | Type     | Intended Task                              |
      | Logo "FreelanceLaunch"           | Link     | Click → stays on /                        |
      | Nav "Topics"                     | Link     | Click → /topics                           |
      | Nav "Sign in"                    | Link     | Click → /auth/login                       |
      | Nav "Get Started"                | Link     | Click → /auth/signup                      |
      | Hero "Start Free" button         | Link     | Click → /auth/signup                      |
      | Hero "Explore Skills" button     | Link     | Click → /topics                           |
      | Topic card 1 (web-scraping)      | Link     | Click → /topics/web-scraping-python       |
      | Topic card 2 (n8n)               | Link     | Click → /topics/n8n-automation            |
      | Topic card 3 (seo)               | Link     | Click → /topics/seo-content-writing       |
      | Topic card 4 (pandas)            | Link     | Click → /topics/data-analysis-pandas      |
      | Topic card 5 (wordpress)         | Link     | Click → /topics/wordpress-development     |
      | "View details and demand data →" | Link     | Click → /topics                           |
      | CTA "Get Started Free"           | Link     | Click → /auth/signup                      |
      | CTA "Browse Skills"              | Link     | Click → /topics                           |
      | Footer "Topics"                  | Link     | Click → /topics                           |
      | Footer "Pricing"                 | Link     | Click → /payments/pricing                 |
    And the page must have zero console errors and zero failed requests


  # 2. TOPICS EXPLORER (/topics)

  Scenario: TOP-1 — Every clickable on /topics performs its task
    Given I visit /topics while logged out
    Then the following clickables must exist and behave as specified:
      | Element                          | Type     | Intended Task                              |
      | Search input                     | Input    | Typing filters topic cards live            |
      | Topic card 1 (web-scraping)      | Link     | Click → /topics/web-scraping-python        |
      | Topic card 2 (n8n)               | Link     | Click → /topics/n8n-automation             |
      | Topic card 3 (seo)               | Link     | Click → /topics/seo-content-writing        |
      | Topic card 4 (pandas)            | Link     | Click → /topics/data-analysis-pandas       |
      | Topic card 5 (wordpress)         | Link     | Click → /topics/wordpress-development      |
    And the page must have zero console errors and zero failed requests

  Scenario: TOP-2 — Search results block (after live search)
    Given I type "web scraping" in the search box
    Then a search results section appears with platform demand data
    And it must contain at most one documented actionable element:
      | Element                          | Type     | Intended Task                              |
      | "Link Platforms" (no platforms)  | Link     | Click → /platforms/setup                   |
      | "Create 30-Day Curriculum"       | Button   | Wiring: POST /enroll/new (click skipped: LLM generation side-effect) |


  # 3. TOPIC DETAIL (/topics/<slug>) — enrolled user

  Scenario: TDET-1 — Every clickable on topic detail performs its task
    Given I am logged in as the test user
    And I visit /topics/web-scraping-python
    Then the following clickables must exist and behave as specified:
      | Element                          | Type     | Intended Task                              |
      | "You're enrolled" banner         | Text     | Visible with green style                    |
      | "Go to Dashboard →"              | Link     | Click → /dashboard/                        |
      | Curriculum day link 1            | Link     | Click → /dashboard/day/1                   |
      | Curriculum day link 2            | Link     | Click → /dashboard/day/2                   |
      | "View curriculum" anchor         | Link     | Click → #curriculum-section (scrolls)      |

  Scenario: TDET-2 — Topic detail while logged out
    Given I am logged out
    And I visit /topics/web-scraping-python
    Then the following clickables must exist and behave as specified:
      | Element                          | Type     | Intended Task                              |
      | "Get Started Free"               | Link     | Click → /auth/signup?topic=web-scraping-python |
      | "Sign in"                        | Link     | Click → /auth/login?topic=web-scraping-python |


  # 4. AUTH PAGES

  Scenario: AUTH-1 — Login page clickables
    Given I visit /auth/login
    Then the following clickables must exist and behave as specified:
      | Element                          | Type     | Intended Task                              |
      | Email input                      | Input    | Accepts an email address                   |
      | Password input                   | Input    | Accepts a password (masked)                |
      | "Sign In" submit                 | Submit   | POST /auth/login → session → /dashboard/   |
      | "Create one"                     | Link     | Click → /auth/signup                       |

  Scenario: AUTH-2 — Login with wrong credentials shows error
    When I submit login with a wrong password
    Then I stay on /auth/login
    And I see an error flash message

  Scenario: AUTH-3 — Signup page clickables
    Given I visit /auth/signup
    Then the following clickables must exist and behave as specified:
      | Element                          | Type     | Intended Task                              |
      | Name input                       | Input    | Required, placeholder present              |
      | Email input                      | Input    | Required, type=email                       |
      | Password input                   | Input    | Required, minlength=6                      |
      | "Create Free Account" submit     | Submit   | Wiring: POST /auth/signup (click skipped: creates a NEW real user) |
      | "Sign in" link                   | Link     | Click → /auth/login                        |

  Scenario: AUTH-4 — Signup duplicate email shows error (submit exercised safely)
    When I fill signup with the existing test email and submit
    Then I stay on /auth/signup
    And I see an "already registered" error

  Scenario: AUTH-5 — Logout clears the session
    Given I am logged in
    When I click "Sign out" in the avatar dropdown
    Then I am redirected to /topics
    And visiting /dashboard/ redirects to /auth/login


  # 5. DASHBOARD (/dashboard/)

  Scenario: DASH-1 — Every clickable on the dashboard performs its task
    Given I am logged in as the test user
    And I visit /dashboard/
    Then the following clickables must exist and behave as specified:
      | Element                          | Type      | Intended Task                              |
      | "Watch today's video" checkbox   | Checkbox  | Click → POST /api/progress/mark → persists after reload |
      | "Complete practice task" checkbox| Checkbox  | Click → POST /api/progress/mark → persists after reload |
      | "Submit your work" checkbox      | Checkbox  | Click → POST /api/progress/mark → persists after reload |
      | "Submit Deliverable →"           | Link      | Click → /deliverables/submit?day=N         |
      | Current day card link            | Link      | Click → /dashboard/day/N                   |
      | Week grid day boxes (7)          | Link      | Each click → /dashboard/day/<n>            |
      | "My Portfolio"                   | Link      | Click → /deliverables/portfolio            |
      | "Track Applications"             | Link      | Click → /freelance/pipeline                |
      | "Upgrade Plan"                   | Link      | Click → /payments/pricing                  |
      | Pipeline card "Manage"           | Link      | Click → /freelance/pipeline                |


  # 6. DAY DETAIL (/dashboard/day/<n>)

  Scenario: DAY-1 — Every clickable on the day page performs its task
    Given I am logged in
    And I visit /dashboard/day/2
    Then the following clickables must exist and behave as specified:
      | Element                          | Type      | Intended Task                              |
      | "← Back to Dashboard"            | Link      | Click → /dashboard/                        |
      | "Play Video Preview" button      | Button    | Click → inline iframe expands below (no new tab) |
      | Preview Minimize button          | Button    | Click → iframe collapses                   |
      | Preview Fullscreen button        | Button    | Click → toggles fullscreen class           |
      | Preview Close button             | Button    | Click → preview closes                     |
      | Progress checkboxes (3)          | Checkbox  | Click → POST /api/progress/mark            |
      | "Start Generation" button        | Button    | Wiring: onclick startGeneration() (click skipped: LLM side-effect) |


  # 7. PIPELINE (/freelance/pipeline)

  Scenario: PIPE-1 — Every clickable on the pipeline performs its task
    Given I am logged in
    And I visit /freelance/pipeline
    Then the following clickables must exist and behave as specified:
      | Element                          | Type      | Intended Task                              |
      | "+1 Proposal Sent"               | Button    | hx-post /freelance/api/update → proposals_sent increments |
      | "I'm Applying Now"               | Button    | hx-post /freelance/api/update → stage becomes applying |
      | Platform select                  | Select    | Options: upwork, fiverr, contra, direct    |
      | Client name input                | Input     | Required for contract add                  |
      | Project title input              | Input     | Required for contract add                  |
      | Contract value input             | Input     | Optional number                            |
      | Hours worked input               | Input     | Optional number                            |
      | "+ Add Contract" submit          | Submit    | POST /freelance/contract/add → contract row created |


  # 8. PORTFOLIO (/deliverables/portfolio)

  Scenario: PORT-1 — Every clickable on the portfolio performs its task
    Given I am logged in
    And I visit /deliverables/portfolio
    Then the following clickables must exist and behave as specified:
      | Element                          | Type      | Intended Task                              |
      | "+ Add Item"                     | Link      | Click → /deliverables/submit               |
      | Deliverable card (if any)        | View      | Renders without error                      |


  # 9. SUBMIT DELIVERABLE (/deliverables/submit)

  Scenario: SUB-1 — Every clickable on the submit page performs its task
    Given I am logged in
    And I visit /deliverables/submit
    Then the following clickables must exist and behave as specified:
      | Element                          | Type      | Intended Task                              |
      | "← Back to Dashboard"            | Link      | Click → /dashboard/                        |
      | Day number input                 | Input     | Number 1-60, required                      |
      | Type select                      | Select    | Options: blog, code, proposal, screenshot, other |
      | Title input                      | Input     | Accepts text                               |
      | Content textarea                 | Textarea  | Accepts multi-line text                    |
      | "Submit for Portfolio"           | Submit    | POST /deliverables/submit → redirects to /dashboard/ with flash |


  # 10. PRICING (/payments/pricing)

  Scenario: PRICE-1 — Pricing clickables (logged out)
    Given I am logged out
    And I visit /payments/pricing
    Then the following clickables must exist and behave as specified:
      | Element                          | Type      | Intended Task                              |
      | Free tier "Get Started Free"     | Link      | Click → /auth/signup                       |
      | Guided "Sign Up to Upgrade"      | Link      | Click → /auth/signup                       |
      | Placement "Sign Up to Upgrade"   | Link      | Click → /auth/signup                       |

  Scenario: PRICE-2 — Pricing clickables (logged in)
    Given I am logged in
    And I visit /payments/pricing
    Then the following clickables must exist and behave as specified:
      | Element                          | Type      | Intended Task                              |
      | Guided "Upgrade"                 | Submit    | Wiring: form action /payments/create-checkout (click skipped: Stripe side-effect) |
      | Placement "Upgrade"              | Submit    | Wiring: form action /payments/create-checkout (click skipped: Stripe side-effect) |


  # 11. PROFILE (/auth/profile)

  Scenario: PROF-1 — Every clickable on the profile performs its task
    Given I am logged in
    And I visit /auth/profile
    Then the following clickables must exist and behave as specified:
      | Element                          | Type      | Intended Task                              |
      | Display name input               | Input     | Shows current name, editable               |
      | "Save" submit                    | Submit    | POST → display_name updates → success flash |


  # 12. PLATFORM SETUP (/platforms/setup)

  Scenario: PLAT-1 — Every clickable on platform setup performs its task
    Given I am logged in
    And I visit /platforms/setup
    Then the following clickables must exist and behave as specified:
      | Element                          | Type      | Intended Task                              |
      | Upwork "+ Link Upwork"           | Button    | POST /platforms/api/select → card flips to pending state |
      | Fiverr "+ Link Fiverr"           | Button    | POST /platforms/api/select → pending state |
      | Contra "+ Link Contra"           | Button    | POST /platforms/api/select → pending state |
      | "Create Upwork Account"          | External  | href = upwork.com signup, target=_blank    |
      | "Create Fiverr Account"          | External  | href = fiverr.com signup, target=_blank    |
      | "Create Contra Account"          | External  | href = contra.com signup, target=_blank    |
      | Step-by-step guide (details)     | Toggle    | Click → expands numbered steps             |
      | "✅ I've done this"              | Button    | POST /platforms/api/verify → status verified |
      | "Skip for now"                   | Button    | POST /platforms/api/skip → status skipped  |
      | "Continue to Dashboard →"        | Link      | Click → /dashboard/                        |


  # 13. ADMIN PAGES

  Scenario: ADM-1 — Admin dashboard clickables
    Given I am logged in as an admin user
    And I visit /admin/
    Then the following clickables must exist and behave as specified:
      | Element                          | Type      | Intended Task                              |
      | "View All Users"                 | Link      | Click → /admin/users                       |
      | "Production Queue"               | Link      | Click → /admin/production                  |

  Scenario: ADM-2 — Admin users page clickables
    Given I am logged in as an admin user
    And I visit /admin/users
    Then the following clickables must exist and behave as specified:
      | Element                          | Type      | Intended Task                              |
      | "← Admin Home"                   | Link      | Click → /admin/                            |

  Scenario: ADM-3 — Admin production page clickables
    Given I am logged in as an admin user
    And I visit /admin/production
    Then the following clickables must exist and behave as specified:
      | Element                          | Type      | Intended Task                              |
      | "← Admin Home"                   | Link      | Click → /admin/                            |
      | "Produce Now" submit             | Submit    | Wiring: form action /admin/production/trigger/<id> (click skipped: render side-effect) |


  # 14. GLOBAL NAVIGATION + FOOTER (every logged-in page)

  Scenario: GLOB-1 — Nav bar and footer clickables on every logged-in page
    Given I am logged in
    And I visit /dashboard/
    Then the following clickables must exist and behave as specified:
      | Element                          | Type      | Intended Task                              |
      | Logo "FreelanceLaunch"           | Link      | Click → /                                  |
      | Nav "Topics"                     | Link      | Click → /topics                            |
      | Nav "Dashboard"                  | Link      | Click → /dashboard/                        |
      | Nav "Pipeline"                   | Link      | Click → /freelance/pipeline                |
      | Nav "Pricing"                    | Link      | Click → /payments/pricing                  |
      | Nav "Link Platforms" badge       | Link      | Click → /platforms/setup                   |
      | Avatar button                    | Button    | Click → opens dropdown                     |
      | Dropdown "Profile"               | Link      | Click → /auth/profile                      |
      | Dropdown "Portfolio"             | Link      | Click → /deliverables/portfolio            |
      | Dropdown "Sign out"              | Link      | Click → /auth/logout                       |
      | Footer "Topics"                  | Link      | Click → /topics                            |
      | Footer "Pricing"                 | Link      | Click → /payments/pricing                  |


  # 15. ROUTING SAFETY NET

  Scenario: SAFE-1 — Protected routes redirect to login when logged out
    When I visit /dashboard/, /freelance/pipeline, /deliverables/portfolio, /auth/profile, /platforms/setup and /admin/ while logged out
    Then each redirects to /auth/login with a next= parameter

  Scenario: SAFE-2 — Unknown route returns a 404 page (not a 500)
    When I visit /definitely-not-a-real-page
    Then I get an HTTP 404 with a rendered error page

  Scenario: SAFE-3 — No console errors on any audited page
    Given I have visited every page in this audit
    Then the collected console log contains no uncaught errors
