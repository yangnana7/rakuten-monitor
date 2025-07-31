Feature: FastAPI Metrics Endpoint
  As a system administrator
  I want to monitor the Rakuten application metrics
  So that I can track performance and health

  Background:
    Given the FastAPI server is running

  Scenario: Access metrics endpoint
    When I request the "/metrics" endpoint
    Then the response status code should be 200
    And the content type should be "text/plain"
    And the response should contain Prometheus metrics

  Scenario: Verify uptime metric is positive
    When I request the "/metrics" endpoint
    Then the response status code should be 200
    And the app_uptime_seconds metric should be a positive number

  Scenario: Verify HTTP request metrics are present
    When I request the "/metrics" endpoint
    Then the response status code should be 200
    And the response should contain HTTP request metrics

  Scenario: Health check endpoint works
    Given the healthz endpoint is available
    When I request the "/healthz" endpoint
    Then the response status code should be 200
    And the healthz response should contain status ok
