Feature: Phase B — Mock Contract (Days 6-10)
  As a sprinter
  I want to fulfill a real anonymized brief under deadline and constraints
  So that I learn fulfillment, not just skills

  Scenario: A capstone brief is derived from a real anonymized job post
    Given an active sprint in phase B
    When I open the mock contract view
    Then I see a capstone brief tied to a job_feed posting
    And the brief has a deadline and budget constraint
    And the brief stores no client PII

  Scenario: Phase C stays locked until the contract passes verification
    Given I have submitted my contract deliverable
    When verification is pending
    Then phase C remains locked
    When verification passes
    Then phase C becomes available

  Scenario: Automated verification for code deliverables
    Given my capstone brief has verification_type "auto"
    When I submit my deliverable
    Then the verification service runs automated acceptance checks
    And the review is recorded in verification_reviews

  Scenario: Peer verification for design/copy deliverables
    Given my capstone brief has verification_type "peer"
    When I submit my deliverable
    Then a peer review is enqueued
    And the review is recorded in verification_reviews
