Feature: FreelanceLaunch Full Application E2E — CRUD Coverage
  As a user or admin
  I want to Create, Read, Update, and Delete data across the platform
  So that the entire application is validated end-to-end

  Background:
    Given a fresh browser session
    And the application is running at https://freelancelaunch.onrender.com
    And test data is seeded in the database

  Scenario: C1 — User creates an account (CREATE auth user + profile)
    Given I am on the signup page
    When I fill in name "Test User", email "testuser@example.com", and password "test123456"
    And I submit the form
    Then a new auth user should be created in Supabase
    And a user_profiles record should be created
    And I should see a success message
    And I should be on the login page

  Scenario: C2 — User enrolls in a topic (CREATE cohort assignment + pipeline)
    Given I am logged in as a fresh user
    When I navigate to the Web Scraping topic detail page
    And I click "Start Learning"
    Then my user_profile should have cohort_id and selected_topic_id set
    And a freelance_pipeline record should be created with stage "exploring"
    And I should be redirected to the dashboard

  Scenario: C3 — User submits a deliverable (CREATE deliverable)
    Given I am logged in and enrolled
    When I navigate to the submit page
    And I enter day "2", type "code", title "My Scraper Script"
    And I paste content "import requests\nprint('hello')"
    And I click submit
    Then a deliverables record should exist with my content
    And I should be redirected to the dashboard

  Scenario: C4 — User logs a won contract (CREATE contract)
    Given I am logged in and on the pipeline page
    When I fill in the "Won a Contract?" form:
      | Platform | upwork |
      | Client   | TestClient Inc |
      | Project  | Data scraping job |
      | Value    | 200 |
      | Hours    | 10 |
    And I click "Add Contract"
    Then a contracts record should be created
    And the pipeline total_earned should increase by 200
    And the contract should appear in the contract history table

  Scenario: C5 — User marks progress (CREATE user_progress)
    Given I am logged in and on the dashboard with a video loaded
    When I check "Watch today's video"
    And I check "Complete practice task"
    And I check "Submit your work"
    Then three user_progress records should exist for this day
    And video_watched, practice_completed, apply_completed should all be TRUE

  Scenario: C6 — Admin triggers video production (CREATE cohort_video)
    Given I am logged in as admin
    When I navigate to the admin production page
    And I click "Produce Now" on a pending video
    Then the cohort_video production_status should change to "scripting" or "rendering"
    And a video_production_log entry should be created

  Scenario: R1 — Landing page shows 5 topic cards (READ topics list)
    When I visit the landing page
    Then I should see the headline "Pick a skill"
    And I should see 5 topic preview cards with icons
    And each card should show job count and hourly rate
    And I should see "Get Started Free" and "Explore Skills" buttons

  Scenario: R2 — Topic detail shows demand metrics (READ topic details)
    When I navigate to /topics/web-scraping-python
    Then I should see the topic name, description, and icon
    And I should see 3 demand metrics: "247 open contracts", "$30/hr avg", "92/100"
    And I should see 5 skill tags
    And I should see a curriculum preview (first 10 days)
    And I should see a "Start Learning" or "Get Started Free" button

  Scenario: R3 — Dashboard shows current day and progress (READ cohort + video + progress)
    Given I am logged in and enrolled with Day 1 complete
    When I visit the dashboard
    Then I should see the cohort name and "Day 2 of 30"
    And I should see Day 1 marked complete in the progress bar
    And I should see the progress checklist with Day 1's video as watched
    And I should see the weekly progress grid
    And I should see the pipeline summary with proposal count

  Scenario: R4 — Pipeline page shows full stats (READ pipeline + contracts)
    Given I am logged in with active pipeline and contracts
    When I navigate to the pipeline page
    Then I should see the stage progress bar (exploring → completed)
    And I should see proposal count, replies, interviews, contracts
    And I should see earned amount
    And I should see contract history table with client names and values
    And I should see the "Won a Contract?" form

  Scenario: R5 — Portfolio page shows submitted work (READ deliverables list)
    Given I have submitted at least 2 deliverables
    When I navigate to my portfolio
    Then I should see all my submitted work as cards
    And each card should show title, type, day number, and date
    And I should see an "Add Item" button
    And I should be able to click a card to view details

  Scenario: R6 — Pricing page shows 3 tiers (READ pricing data)
    When I navigate to /payments/pricing
    Then I should see "Free" tier with 3 features
    And I should see "Guided Accelerator" at $49 — marked "Most Popular"
    And I should see "Placement Program" at $199
    And free tier should show "Get Started Free" button

  Scenario: R7 — Admin dashboard shows platform metrics (READ admin stats)
    Given I am logged in as admin
    When I navigate to /admin
    Then I should see total users count
    And I should see cohorts count
    And I should see paid users count
    And I should see recent signups list
    And I should see active cohorts list

  Scenario: R8 — Admin user list shows all users (READ users table)
    Given I am logged in as admin
    When I navigate to /admin/users
    Then I should see a table with user rows
    And each row should show: name, tier, topic, creation date
    And tier should be color-coded (free=gray, guided=blue, placement=purple)

  Scenario: R9 — Admin production queue shows video statuses (READ cohort_videos)
    Given I am logged in as admin
    When I navigate to /admin/production
    Then I should see pending videos in the "Pending" section
    And I should see recent productions with status badges
    And the nightly cron schedule should be displayed
    And "Produce Now" buttons should be visible for pending items

  Scenario: R10 — Profile page shows user stats (READ user_profile + pipeline)
    Given I am logged in with pipeline data
    When I navigate to /auth/profile
    Then I should see my display name and email
    And I should see my current tier badge
    And I should see pipeline summary cards (proposals, contracts, earned, stage)

  Scenario: U1 — User updates profile name (UPDATE user_profiles)
    Given I am logged in
    When I navigate to my profile
    And I change my display name to "Updated Name"
    And I click Save
    Then the user_profiles display_name should be "Updated Name"
    And a success flash message should appear

  Scenario: U2 — User increments proposal count (UPDATE freelance_pipeline)
    Given I am logged in and on the pipeline page
    When I click "+1 Proposal Sent"
    Then the proposals_sent count should increment by 1
    And the response should be a JSON success

  Scenario: U3 — User advances pipeline stage (UPDATE pipeline stage)
    Given I am logged in with pipeline at stage "learning"
    When I click "I'm Applying Now"
    Then the pipeline stage should change to "applying"
    And the page should reflect the new stage

  Scenario: U4 — User updates contract status (UPDATE contract)
    Given I have an active contract
    When I update the contract status to "completed"
    Then the contract status should be "completed"
    And the pipeline contracts_completed should increment

  Scenario: U5 — Admin marks video as ready (UPDATE cohort_video)
    Given I am logged in as admin
    And there is a pending cohort_video
    When the production completes successfully
    Then the cohort_video status should change to "ready"
    And youtube_url and youtube_title should be populated

  Scenario: U6 — Cohort advances to next day (UPDATE cohort current_day)
    Given an active cohort at Day 2
    When the overnight scheduler runs
    Then the cohort current_day should advance to 3
    And a new cohort_video for Day 4 should be created

  Scenario: D1 — Session cleared on logout (DELETE session)
    Given I am logged in
    When I click logout from the profile menu
    Then my session should be cleared
    And I should be redirected to the landing page
    And I should not see the dashboard link in navigation
    And visiting /dashboard should redirect to login

  Scenario: D2 — Admin can remove a failed production (DELETE cohort_video)
    Given I am logged in as admin
    And there is a cohort_video with status "failed"
    When I delete the failed video record
    Then the cohort_video should be removed from the database
    And it should no longer appear in the production queue

  Scenario: D3 — User unmarks a progress checkbox (DELETE progress flag — set to FALSE)
    Given I have marked "video_watched" for a day
    When I uncheck the checkbox
    Then user_progress.video_watched should be FALSE
    And the checkbox should appear unchecked on reload

  Scenario: E1 — Login with wrong password shows error
    When I attempt to log in with email "chinaindiatesting@gmail.com" and password "wrongpass"
    Then I should see an error message "Invalid email or password"
    And I should remain on the login page

  Scenario: E2 — Access protected route without login redirects
    When I try to visit /dashboard without logging in
    Then I should be redirected to /auth/login
    And the URL should contain "next=/dashboard"
# After I log in, I should be redirected back to /dashboard

  Scenario: E3 — Enroll in topic without login redirects
    When I try to POST /topics/web-scraping-python/enroll without being logged in
    Then I should be redirected to /auth/login
    And a flash message should not indicate success

  Scenario: E4 — Duplicate email signup shows error
    When I try to sign up with email "chinaindiatesting@gmail.com"
    Then I should see an error message about email already registered

  Scenario: E5 — Submit deliverable without content
    Given I am logged in
    When I submit a deliverable with empty content
    Then the form should not submit or show a validation error
    And no empty deliverable should be created in the database

  # Table               Create  Read  Update  Delete
  # # # # # # # # # # # # # # # # # 
  # auth.users           C1      —     —       D1
  # user_profiles        C1      R10   U1      —
  # topics               —       R1,R2 —       —
  # curricula            —       —     —       —
  # curriculum_days      —       —     —       —
  # cohorts              C6      R3    U6      —
  # cohort_videos        C6      R9    U5      D2
  # freelance_pipeline   C2      R4,R10 U2,U3  —
  # contracts            C4      R4    U4      —
  # deliverables         C3      R5    —       —
  # user_progress        C5      R3    D3      —
  # user_acquisition     —       R7    —       —
  # topic_intelligence   —       —     —       —
  # video_production_log C6      —     —       —
  # session              —       —     —       D1
