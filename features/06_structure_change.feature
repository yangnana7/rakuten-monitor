Feature: Structure Change Chaos Testing
  Testing system resilience when HTML structure changes

  Background:
    Given the monitoring system is initialized
    And Prometheus metrics are available

  Scenario: HTML structure change detected
    Given the HTML structure has been damaged
    When the monitor runs once
    Then a layout error should be caught
    And the monitor_fail_total metric should increase for type "layout"
    And an error notification should be sent
