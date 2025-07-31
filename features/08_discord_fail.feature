Feature: Discord Notification Failure Chaos Testing
  Testing system resilience when Discord webhook fails

  Background:
    Given the monitoring system is initialized
    And Prometheus metrics are available

  Scenario: Discord webhook returns 500 error
    Given the Discord webhook is mocked to return 500 error
    When the monitor runs once with a new product
    Then a Discord error should be caught
    And the monitor_fail_total metric should increase for type "discord"
    And the system should handle the failure gracefully
