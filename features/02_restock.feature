Feature: Notify Discord when a previously sold-out item is restocked

  Background:
    Given the environment variable "START_TIME" is "08:00"
      And the environment variable "END_TIME" is "20:00"
      And the Rakuten HTML fixture "item_restock.html" is served at LIST_URL
      And the item "shouritu-100071" already exists in the database as sold-out

  Scenario: Detect restock and send a message
    When I run the monitor
    Then Discord receives a message containing "restock" and "shouritu-100071"
    And the database marks "shouritu-100071" as "open"
