Feature: Notify Discord when the website is unreachable

  Background:
    Given the environment variable "START_TIME" is "08:00"
      And the environment variable "END_TIME" is "20:00"
      And the LIST_URL returns a 404 error

  Scenario: Website unreachable, send error notification
    When I run the monitor
    Then Discord receives a message containing "error" and "connection"
    And no database changes are made
