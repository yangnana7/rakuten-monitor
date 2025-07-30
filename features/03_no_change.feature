Feature: No catalogue changes
  Background:
    Given the monitor target URL is set
    And a Discord Webhook URL is configured
    And previous run data (item list & stock state) exists

  Scenario: Nothing changed
    Given the product lineup and all product stock states are identical to the previous run
    When the monitor checks the page
    Then no action should be taken
      And no Discord notification should be sent
