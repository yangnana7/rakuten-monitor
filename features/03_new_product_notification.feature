@bdd
Feature: New product notification
  As a user
  I want to be notified when new products are available
  So that I can quickly purchase items I'm interested in

  Background:
    Given the database.json state file exists
    And the environment variable "START_TIME" is set to "08:00"
    And the environment variable "END_TIME" is set to "20:00"
    And the environment variable "DISCORD_WEBHOOK_URL" is set to a valid webhook URL
    And the current time is within the monitoring window

  Scenario: Notify when new in-stock product is discovered
    Given a monitoring URL has a new product that was not in the previous check
    And the new product is "in stock"
    When the monitoring tool checks the page
    Then a Discord notification should be sent with format "【新商品】[product_name]が入荷しました！ [price] [product_url]"
    And the new product information should be recorded in database.json
