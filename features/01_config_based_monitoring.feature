@bdd
Feature: Configuration-based monitoring
  As a developer
  I want the monitoring tool to work based on environment variables
  So that I can change monitoring behavior without editing source code

  Background:
    Given the database.json state file exists
    And the monitoring tool is properly configured

  Scenario: Execute monitoring based on environment variables
    Given the environment variable "LIST_URL" is set to "https://item.rakuten.co.jp/shop-a/product-1/"
    And the environment variable "START_TIME" is set to "08:00"
    And the environment variable "END_TIME" is set to "20:00"
    And the environment variable "DISCORD_WEBHOOK_URL" is set to a valid webhook URL
    And the current time is within "08:00" to "20:00"
    When the monitoring tool is executed by cron
    Then product information should be checked for all configured URLs
    And the monitoring process should complete successfully
