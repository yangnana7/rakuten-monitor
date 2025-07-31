Feature: Database Failure Chaos Testing
  Testing system resilience when database operations fail

  Background:
    Given the monitoring system is initialized
    And Prometheus metrics are available

  Scenario: Database write failure occurs
    Given the database connection is mocked to fail
    When the monitor runs once with valid data
    Then a database error should be caught
    And the monitor_fail_total metric should increase for type "db"
    And a database error notification should be sent
