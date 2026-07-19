Feature: All Buttons and Links — E2E Behavior Audit
  As a user
  I want every button and link on every page to work correctly
  So that the application behaves as expected

  Background:
    Given the application is running at https://freelancelaunch.onrender.com

  ═══════════════════════════════════════════════════════════
  LANDING PAGE (/)
  ═══════════════════════════════════════════════════════════

  Scenario: Landing page buttons and links
    When I visit the landing page
    Then I should see the following and verify behavior:
      | Element | Type | Expected Behavior |
      | "FreelanceLaunch" logo text | Link | Click → stays on / |
      | "Topics" nav link | Link | Click → navigates to /topics |
      | "Sign in" nav link | Link | Click → navigates to /auth/login |
      | "Get Started" nav button | Link | Click → navigates to /auth/signup |
      | "Explore Skills" hero button | Link | Click → navigates to /topics |
      | "Start Free" hero button | Link | Click → navigates to /auth/signup |
      | Skill preview cards (5) | Link | Click → navigates to /topics/<slug> |
      | "View all topics →" link | Link | Click → navigates to /topics |
      | "Get Started Free" CTA button | Link | Click → navigates to /auth/signup |
      | "Browse Skills" CTA button | Link | Click → navigates to /topics |
      | "Pricing" footer link | Link | Click → navigates to /payments/pricing |

  ═══════════════════════════════════════════════════════════
  TOPICS EXPLORER (/topics)
  ═══════════════════════════════════════════════════════════

  Scenario: Topics page buttons and links (logged out)
    When I visit /topics while logged out
    Then I should see and verify:
      | Element | Type | Expected Behavior |
      | Search input | Input | Typing filters topic cards in real-time |
      | "Search" button | Button | Click → calls /search/api with query, shows platform demand results |
      | "Market Demand" result card | Div | Shows Upwork, Fiverr, Contra jobs + rates per search |
      | "Create 30-Day Curriculum" button | Button | Click → POST /enroll/new, generates LLM curriculum, creates cohort, redirects to /platforms/setup |
      | "Visit →" platform link | External Link | Opens upwork.com/fiverr.com/contra.com in new tab |
      | 5 topic cards | Link | Each click → navigates to /topics/<slug> |
      | "Web Scraping with Python" card | Link | Click → /topics/web-scraping-python |
      | "n8n Workflow Automation" card | Link | Click → /topics/n8n-automation |
      | "SEO Content Writing" card | Link | Click → /topics/seo-content-writing |
      | "Data Analysis with Pandas" card | Link | Click → /topics/data-analysis-pandas |
      | "Basic WordPress Development" card | Link | Click → /topics/wordpress-development |

  ═══════════════════════════════════════════════════════════
  TOPIC DETAIL (/topics/<slug>)
  ═══════════════════════════════════════════════════════════

  Scenario: Topic detail page buttons and links (logged out)
    When I visit /topics/web-scraping-python while logged out
    Then I should see and verify:
      | Element | Type | Expected Behavior |
      | Skill icon + name | Header | Displays correct icon and name |
      | Trend badge | Badge | Shows "Growing" or "Stable" |
      | 3 demand metric cards | Cards | Show: job count ($247), avg rate ($30/hr), demand score (92/100) |
      | Skill tags | Tags | Show: Python, HTTP, HTML/CSS, JSON, APIs |
      | Difficulty + timeline | Text | Shows "Beginner-Intermediate" and "~3 weeks to first gig" |
      | "Get Started Free" button | Link | Click → /auth/signup?topic=web-scraping-python |
      | "Sign in" link | Link | Click → /auth/login?next=/topics/web-scraping-python |
      | Curriculum preview (10 days) | List | Shows Day 1-10 with titles |
      | "Full curriculum unlocks when you enroll" | Text | Visible below preview |

  Scenario: Topic detail buttons and links (logged in, not enrolled)
    Given I am logged in but not enrolled in this topic
    When I visit /topics/web-scraping-python
    Then I should see:
      | Element | Type | Expected Behavior |
      | "Start Learning Web Scraping with Python" | Submit Button | Click → POST /topics/web-scraping-python/enroll, creates pipeline, redirects to /platforms/setup |
      | "Free tier includes full curriculum" | Text | Visible below button |
      | Curriculum preview | List | Shows 10 days |

  Scenario: Topic detail when already enrolled
    Given I am logged in and enrolled in web-scraping-python
    When I visit /topics/web-scraping-python
    Then I should see:
      | Element | Type | Expected Behavior |
      | "You're enrolled" message | Alert | Shows green with "Go to Dashboard →" link |
      | "Go to Dashboard →" link | Link | Click → /dashboard/ |

  ═══════════════════════════════════════════════════════════
  AUTH PAGES
  ═══════════════════════════════════════════════════════════

  Scenario: Signup page buttons and links
    When I visit /auth/signup
    Then I should see and verify:
      | Element | Type | Expected Behavior |
      | Name input | Input | Required, placeholder "Your name" |
      | Email input | Input | Required, type=email, placeholder "you@example.com" |
      | Password input | Input | Required, minlength=6 |
      | Hidden topic input | Hidden | Present only if ?topic= param set |
      | "Create Free Account" button | Submit | Click → POST /auth/signup, creates auth user + profile, redirects to /auth/login |
      | "Login" link | Link | Click → /auth/login |
      | "Start your freelance journey" heading | Text | Visible |

  Scenario: Login page buttons and links
    When I visit /auth/login
    Then I should see and verify:
      | Element | Type | Expected Behavior |
      | Email input | Input | Required |
      | Password input | Input | Required |
      | "Sign In" button | Submit | Click → POST /auth/login, sets session, redirects to /dashboard/ |
      | "Create one" link | Link | Click → /auth/signup |

  Scenario: Login with wrong credentials
    When I submit login with wrong password
    Then I should stay on /auth/login
    And see error flash message "Invalid email or password"

  ═══════════════════════════════════════════════════════════
  DASHBOARD (/dashboard/)
  ═══════════════════════════════════════════════════════════

  Scenario: Dashboard buttons and links (logged in, enrolled)
    Given I am logged in and enrolled with cohort
    When I visit /dashboard/
    Then I should see and verify:
      | Element | Type | Expected Behavior |
      | Cohort name heading | Text | Shows cohort name |
      | "Day X of 30" | Text | Shows current day |
      | Days completed count | Text | Shows "X/30 days completed" |
      | Progress bar | Visual | Width = (completed/total)*100% |
      | "Day X: Title" heading | Text | Shows current day + lesson title |
      | "Video Ready" badge | Badge | Green if video exists |
      | Video player iframe | Iframe | Shows YouTube embed if video ready |
      | "Video pending" placeholder | Div | Shows "rendering overnight" if no video |
      | "Watch today's video" checkbox | Checkbox | Click → POST /api/progress/mark, sets video_watched=true |
      | "Complete practice task" checkbox | Checkbox | Click → POST /api/progress/mark, sets practice_completed=true |
      | "Submit your work" checkbox | Checkbox | Click → POST /api/progress/mark, sets apply_completed=true |
      | "Submit Deliverable →" button | Link | Click → /deliverables/submit?day=X |
      | "Your Pipeline" card | Card | Shows stage, proposals, contracts, earned |
      | "Manage" link | Link | Click → /freelance/pipeline |
      | "This Week" grid | Grid | Shows 7 day boxes, current day highlighted |
      | "My Portfolio" link | Link | Click → /deliverables/portfolio |
      | "Track Applications" link | Link | Click → /freelance/pipeline |
      | "Upgrade Plan" link | Link | Click → /payments/pricing |
      | Nav: Dashboard | Link | Click → /dashboard/ |
      | Nav: Pipeline | Link | Click → /freelance/pipeline |
      | Nav: 🔗 Link Platforms | Link | Amber if unlinked, green if linked → Click → /platforms/setup |
      | Nav: Avatar dropdown | Dropdown | Shows Profile, Link Platforms, Portfolio, Sign out |

  ═══════════════════════════════════════════════════════════
  PIPELINE (/freelance/pipeline)
  ═══════════════════════════════════════════════════════════

  Scenario: Pipeline page buttons and links
    Given I am logged in with pipeline data
    When I visit /freelance/pipeline
    Then I should see and verify:
      | Element | Type | Expected Behavior |
      | Pipeline stage badges | Badge | Color-coded (applying=blue, contracted=green, etc.) |
      | Stage progress bar | Visual | 8 segments, filled for completed stages |
      | 4 stat cards | Cards | Proposals sent, replies, interviews, contracts |
      | "💰 $X earned" | Alert | Green if >0 |
      | "+1 Proposal Sent" button | HTMX Button | Click → POST /freelance/api/update, increments proposals_sent |
      | "I'm Applying Now" button | HTMX Button | Click → POST /freelance/api/update, changes stage to "applying" |
      | Platform dropdown | Select | Options: Upwork, Fiverr, Contra, Direct Client |
      | Client name input | Input | Required |
      | Project title input | Input | Required |
      | Contract value input | Input | Number, optional |
      | Hours worked input | Input | Number, optional |
      | "+ Add Contract" button | Submit | Click → POST /freelance/contract/add, creates contract, updates earnings |
      | "Stay consistent" card | Card | Gradient purple with motivational text |
      | Contract history table | Table | Shows client, project, platform, value, status |
      | Completed status badge | Badge | Green for completed |
      | Active status badge | Badge | Blue for active |

  ═══════════════════════════════════════════════════════════
  PORTFOLIO (/deliverables/portfolio)
  ═══════════════════════════════════════════════════════════

  Scenario: Portfolio page buttons and links
    Given I am logged in
    When I visit /deliverables/portfolio
    Then I should see and verify:
      | Element | Type | Expected Behavior |
      | "My Portfolio" heading | Text | Shows page title |
      | "+ Add Item" button | Link | Click → /deliverables/submit |
      | Deliverable cards | Cards | Shows title, type, day number, date |
      | "Submit Your First Piece" button | Link | Visible only if portfolio empty → click → /deliverables/submit |
      | "No portfolio items yet" message | Text | Visible only if portfolio empty |

  Scenario: Submit deliverable page
    When I visit /deliverables/submit
    Then I should see and verify:
      | Element | Type | Expected Behavior |
      | "← Back to Dashboard" link | Link | Click → /dashboard/ |
      | Day number input | Input | Number, 1-60, required |
      | Type dropdown | Select | Options: Blog Post, Code, Proposal, Screenshot, Other |
      | Title input | Input | Text, optional |
      | Content textarea | Textarea | Multi-line, optional |
      | "Submit for Portfolio" button | Submit | Click → POST /deliverables/submit, creates deliverable, redirects to /dashboard/ |

  ═══════════════════════════════════════════════════════════
  PRICING (/payments/pricing)
  ═══════════════════════════════════════════════════════════

  Scenario: Pricing page buttons and links (logged out)
    When I visit /payments/pricing
    Then I should see and verify:
      | Element | Type | Expected Behavior |
      | Free tier card | Card | Shows "Free" with 3 features |
      | "Get Started Free" button | Link | Click → /auth/signup |
      | Guided tier card | Card | Shows "Guided Accelerator $49" with "MOST POPULAR" badge |
      | "Sign Up to Upgrade" button | Link | Click → /auth/signup |
      | Placement tier card | Card | Shows "Placement Program $199" with 5 features |
      | Feature checkmarks | List | ✓ for each feature |

  Scenario: Pricing page buttons (logged in, free tier)
    Given I am logged in with free tier
    When I visit /payments/pricing
    Then "Get Guided Accelerator" button | Submit | Click → POST /payments/create-checkout with tier=guided |
    And "Get Placement Program" button | Submit | Click → POST /payments/create-checkout with tier=placement |

  ═══════════════════════════════════════════════════════════
  PLATFORM SETUP (/platforms/setup)
  ═══════════════════════════════════════════════════════════

  Scenario: Platform setup page buttons and links
    Given I am logged in
    When I visit /platforms/setup
    Then I should see and verify:
      | Element | Type | Expected Behavior |
      | Upwork card | Card | Shows 💼, name, about text |
      | "+ Link Upwork" button | Button | Click → POST /platforms/api/select, creates pending record |
      | Fiverr card | Card | Shows 🎯, name, about text |
      | "+ Link Fiverr" button | Button | Same pattern |
      | Contra card | Card | Shows ⚡, name, about text |
      | "+ Link Contra" button | Button | Same pattern |
      | After linking: "Create X Account" deep link | External Link | Opens platform signup page in new tab |
      | "Show step-by-step guide" | Details | Expandable with numbered steps |
      | "✅ I've done this" button | Button | Click → POST /platforms/api/verify, marks verified |
      | "Skip for now" button | Button | Click → POST /platforms/api/skip |
      | Progress bar | Visual | Shows X/3 linked percentage |
      | "Continue to Dashboard →" button | Link | Click → /dashboard/ |
      | Nav: 🔗 Link Platforms badge | Link | Shows green with count if linked |

  ═══════════════════════════════════════════════════════════
  PROFILE (/auth/profile)
  ═══════════════════════════════════════════════════════════

  Scenario: Profile page buttons and links
    Given I am logged in
    When I visit /auth/profile
    Then I should see and verify:
      | Element | Type | Expected Behavior |
      | "Your Profile" heading | Text | |
      | Display name input | Input | Editable, shows current name |
      | Email field | Input | Disabled, shows email |
      | Current tier badge | Badge | Shows free/guided/placement |
      | "Save" button | Submit | Click → updates user_profiles display_name, shows flash |
      | Pipeline summary cards (4) | Cards | Shows proposals, contracts, earned, stage |
      | "Link Platforms" nav dropdown item | Link | Click → /platforms/setup |
      | "Sign out" nav dropdown item | Link | Click → /auth/logout, clears session, redirects to /topics |

  ═══════════════════════════════════════════════════════════
  ADMIN PAGES
  ═══════════════════════════════════════════════════════════

  Scenario: Admin dashboard buttons and links
    Given I am logged in as admin
    When I visit /admin/
    Then I should see and verify:
      | Element | Type | Expected Behavior |
      | 3 stat cards | Cards | Shows: Total Users, Cohorts, Paid Users counts |
      | "Recent Signups" section | List | Shows source + topic + date |
      | "Active Cohorts" section | List | Shows cohort name + day progress |
      | "View All Users" link | Link | Click → /admin/users |
      | "Production Queue" link | Link | Click → /admin/production |

  Scenario: Admin users page
    When I visit /admin/users
    Then I should see and verify:
      | Element | Type | Expected Behavior |
      | "← Admin Home" link | Link | Click → /admin/ |
      | Users table | Table | Columns: Name, Tier, Topic, Cohort, Created |
      | Tier color badges | Badges | Free=gray, Guided=blue, Placement=purple |

  Scenario: Admin production page
    When I visit /admin/production
    Then I should see and verify:
      | Element | Type | Expected Behavior |
      | "⏳ Pending" section | List | Shows videos with status "pending" |
      | "Produce Now" button | Submit | Click → POST /admin/production/trigger/<id>, starts render thread, shows flash |
      | "📋 Recent" section | List | Shows recent productions with color-coded status badges |
      | Green badge "ready" | Badge | Shows for completed videos |
      | Red badge "failed" | Badge | Shows for failed videos |
      | Code block with cron command | Code | Shows nightly schedule |

  ═══════════════════════════════════════════════════════════
  NAVIGATION BAR (present on ALL pages when logged in)
  ═══════════════════════════════════════════════════════════

  Scenario: Navigation bar elements (logged in)
    Given I am logged in
    When I view any page
    Then the nav bar should show:
      | Element | Type | Expected Behavior |
      | "FreelanceLaunch" logo | Link | Click → / |
      | "Topics" | Link | Click → /topics |
      | "Dashboard" | Link | Click → /dashboard/ |
      | "Pipeline" | Link | Click → /freelance/pipeline |
      | "Pricing" | Link | Click → /payments/pricing |
      | 🔗 "Link Platforms" (amber) or "Platforms" (green) | Link | Amber=no platforms linked, green=linked → click → /platforms/setup |
      | Avatar circle with initial | Button | Shows first letter of name/email → opens dropdown |
      | Dropdown: "Profile" | Link | Click → /auth/profile |
      | Dropdown: "🔗 Link Platforms" | Link | Click → /platforms/setup |
      | Dropdown: "Portfolio" | Link | Click → /deliverables/portfolio |
      | Dropdown: "Sign out" | Link | Click → /auth/logout |

  Scenario: Navigation bar elements (logged out)
    Given I am logged out
    When I view any page
    Then the nav bar should show:
      | Element | Type | Expected Behavior |
      | "FreelanceLaunch" logo | Link | Click → / |
      | "Topics" | Link | Click → /topics |
      | "Sign in" | Link | Click → /auth/login |
      | "Get Started" button | Link | Click → /auth/signup |

  ═══════════════════════════════════════════════════════════
  FOOTER (present on ALL pages)
  ═══════════════════════════════════════════════════════════

  Scenario: Footer links
    When I scroll to the footer of any page
    Then I should see:
      | Element | Type | Expected Behavior |
      | "FreelanceLaunch" logo text | Text | Gradient text |
      | "Learn a skill. Land a client. Earn your freedom." | Text | Tagline |
      | "Topics" link | Link | Click → /topics |
      | "Pricing" link | Link | Click → /payments/pricing |

  ═══════════════════════════════════════════════════════════
  SEO META & ERROR PAGES
  ═══════════════════════════════════════════════════════════

  Scenario: Protected routes redirect to login
    When I visit /dashboard/ or /freelance/pipeline or /admin/ without logging in
    Then I should be redirected to /auth/login
    And the URL should contain "next=" parameter pointing back

  Scenario: 404 for unknown routes
    When I visit /some-nonexistent-page
    Then I should get a 404 response

  ═══════════════════════════════════════════════════════════
  BUTTON & LINK COUNT VERIFICATION
  ═══════════════════════════════════════════════════════════

  Scenario: Total interactive elements count per page
    When I visit each page
    Then the following minimum interactive elements should exist:
      | Page | Min Buttons | Min Links | Min Inputs |
      | / | 2 | 10 | 0 |
      | /topics | 1 | 8 | 1 |
      | /topics/<slug> | 1 | 5 | 0 |
      | /auth/login | 1 | 2 | 2 |
      | /auth/signup | 1 | 1 | 3 |
      | /dashboard/ | 3 | 8 | 0 |
      | /freelance/pipeline | 5 | 5 | 5 |
      | /deliverables/portfolio | 1 | 2 | 0 |
      | /deliverables/submit | 1 | 1 | 4 |
      | /payments/pricing | 0 | 3 | 0 |
      | /auth/profile | 1 | 0 | 1 |
      | /admin/ | 0 | 2 | 0 |
      | /admin/production | 1 | 1 | 0 |
      | /platforms/setup | 3 | 4 | 0 |
