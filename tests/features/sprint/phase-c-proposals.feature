Feature: Phase C — Proposals & First Bid (Days 11-14)
  As a sprinter
  I want an engineered proposal and a live bidding challenge
  So that I convert my skill into interviews

  Scenario: A proposal template is generated with job-specific hooks
    Given an active sprint in phase C
    When I open the proposal builder
    Then I see a proposal with "I see you need X…" hooks from my cluster
    And the proposal references my verified mock contract as proof

  Scenario: First-Bid challenge tracks 5 live proposals
    Given the First-Bid challenge is active
    When I submit a proposal to a live job
    Then proposals_sent increments in freelance_pipeline
    And the challenge shows my progress out of 5

  Scenario: Proposals are human-initiated, never auto-submitted
    Given I have a drafted proposal
    When I click "copy" and paste it into the platform
    Then the status changes to "submitted" only on my confirmation

  Scenario: Iteration loop diagnoses a stall
    Given I have submitted 5 proposals
    And I have received no interviews
    When the sprint reaches day 14
    Then the iteration engine diagnoses price, portfolio, or niche
    And I am assigned a 2-hour remedial micro-course
