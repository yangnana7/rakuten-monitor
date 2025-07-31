Feature: Notify Discord when a new product is detected

  Background:
    Given the environment variable "START_TIME" is "08:00"
      And the environment variable "END_TIME" is "20:00"
      And the Rakuten HTML fixture "item_new_product.html" is served at LIST_URL
      And the database is empty

  Scenario: Detect new product and send a message
    When I run the monitor
    Then Discord receives a message containing "New Product" and the new item code
    And the database contains the new item as "open"
