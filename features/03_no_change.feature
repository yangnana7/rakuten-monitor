Feature: No Discord notification when there are no changes

  Background:
    Given the environment variable "START_TIME" is "08:00"
      And the environment variable "END_TIME" is "20:00"
      And the Rakuten HTML fixture "item_no_change.html" is served at LIST_URL
      And the item "existing-item-001" already exists in the database as "open"

  Scenario: No changes detected, no message sent
    When I run the monitor
    Then Discord receives no messages
    And the database item "existing-item-001" remains unchanged
