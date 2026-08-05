Feature: Freelance Platform Account Verification
  As a new user
  I want to verify my freelance platform accounts (Upwork, Fiverr, Contra)
  So that I can apply to real jobs and track accurate contract information

  Background:
    Given I am a logged-in user enrolled in a topic
    And I am on the onboarding step for platform setup

  #  CREATE & LINK PLATFORM ACCOUNTS # # # # # # # ─

  Scenario: C1 — User selects a freelance platform
    Given I see 3 platform options: Upwork, Fiverr, Contra
    When I select "Upwork" from the platform dropdown
    Then a user_platforms record should be created with status "pending"
    And I should see a deep link to create an Upwork account

  Scenario: C2 — User selects multiple platforms
    When I select "Upwork" and "Fiverr" from the platform dropdown
    Then two user_platforms records should be created
    And each should have status "pending"
    And I should see deep links for both platforms

  Scenario: C3 — User marks a platform as set up
    Given I have selected "Upwork" as a platform
    When I click the "I've created my account" button for Upwork
    Then the user_platforms record should update to status "verified"
    And the platform should show a green checkmark

  #  READ PLATFORM STATUS # # # # # # # # # # # 

  Scenario: R1 — Onboarding shows platform cards with deep links
    When I navigate to the platform setup page
    Then I should see 3 platform cards, one for each freelance marketplace
    And each card should show:
      | Platform | Deep Link |
      | Upwork   | https://www.upwork.com/signup/ |
      | Fiverr   | https://www.fiverr.com/signup/ |
      | Contra   | https://contra.com/signup/ |
    And each card should have a "I've done this" verification button

  Scenario: R2 — Dashboard shows platform verification status
    Given I have verified "Upwork" but not "Fiverr"
    When I view my dashboard
    Then I should see "Upwork" with a verified badge
    And I should see "Fiverr" with a "Set up now" prompt
    And clicking "Set up now" should show the deep link

  Scenario: R3 — Pipeline page filters by platform
    Given I have contracts on Upwork and Fiverr
    When I view my pipeline page
    Then I should see a platform filter dropdown
    And selecting "Upwork" should show only Upwork contracts
    And selecting "All" should show all contracts

  #  UPDATE PLATFORM VERIFICATION # # # # # # # # ─

  Scenario: U1 — User changes their platform selection
    Given I have selected "Upwork" and "Fiverr"
    When I deselect "Fiverr" from my platforms
    Then the Fiverr user_platforms record should be removed
    And "Fiverr" should no longer appear in my active platforms

  Scenario: U2 — User retries failed platform creation
    Given I marked "Upwork" as verified but it wasn't really
    When I click "I need help" on the Upwork card
    Then I should see the deep link again
    And the platform status should reset to "pending"

  #  ERROR HANDLING # # # # # # # # # # # # ──

  Scenario: E1 — Platform dropdown prevents empty selection
    When I try to proceed without selecting any platform
    Then I should see an error: "Select at least one platform"
    And I should stay on the platform setup page

  Scenario: E2 — Deep link opens in new tab
    Given I click on a deep link for "Upwork"
    Then the link should open https://www.upwork.com/signup/ in a new tab
    And the current page should remain on FreelanceLaunch

  #  WHAT HAPPENS WITHOUT VERIFIED PLATFORMS # # # # ──

  Scenario: W1 — Job application tracking blocked without accounts
    Given I have no verified platforms
    When I try to add a contract or track a proposal
    Then I should see a message: "Link a freelance platform first"
    And I should be redirected to the platform setup page

  Scenario: W2 — Deep link assistance for each platform
    Given I selected "Contra" as my platform
    When I click "Help me set up"
    Then I should see step-by-step guidance:
      | 1. Click the deep link to open Contra |
      | 2. Sign up with your email |
      | 3. Complete your profile |
      | 4. Return here and click verified |
    And a direct link to https://contra.com/signup/

  #  CRUD COVERAGE # # # # # # # # # # # # ──

  # Table: user_platforms
  # Create:  C1, C2
  # Read:    R1, R2, R3
  # Update:  C3, U2
  # Delete:  U1
  # Total:   12 scenarios
