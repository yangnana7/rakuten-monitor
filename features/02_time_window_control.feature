@bdd
Feature: Time window control
  As a system administrator
  I want the monitoring tool to respect configured time windows
  So that monitoring only occurs during business hours

  Background:
    Given the database.json state file exists
    And the monitoring tool is properly configured

  Scenario: Skip monitoring outside configured time window
    Given the environment variable "START_TIME" is set to "08:00"
    And the environment variable "END_TIME" is set to "20:00"
    And the environment variable "DISCORD_WEBHOOK_URL" is set to a valid webhook URL
    And the current time is "07:59" or "20:01" (outside monitoring window)
    When the monitoring tool is executed by cron
    Then no URL access or product checking should be performed
    And the tool should exit quietly without errors
