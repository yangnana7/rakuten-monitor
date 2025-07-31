@bdd
Feature: Restock notification
  As a user
  I want to be notified when out-of-stock products become available again
  So that I can purchase items that were previously unavailable

  Background:
    Given the database.json state file exists
    And the environment variable "START_TIME" is set to "08:00"
    And the environment variable "END_TIME" is set to "20:00"
    And the environment variable "DISCORD_WEBHOOK_URL" is set to a valid webhook URL
    And the current time is within the monitoring window

  Scenario: Notify when out-of-stock product is restocked
    Given a product was recorded as "out of stock" in database.json
    And the same product is now "in stock" during current monitoring
    When the monitoring tool checks the page
    Then a Discord notification should be sent with format "【再販】[product_name]の在庫が復活しました！ [price] [product_url]"
    And the product status in database.json should be updated to "in stock"
