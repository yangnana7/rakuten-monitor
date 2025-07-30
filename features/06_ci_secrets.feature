Feature: CI & secrets governance
  Background:
    Given source code is managed in a GitHub repository
    And GitHub Actions workflows are configured

  Scenario: CI pipeline enforces tests & secrets
    Given source code is pushed to the GitHub repository
    When GitHub Actions workflow is triggered
    Then all TDD-created tests should run automatically in a clean virtual environment (e.g., Ubuntu)
      And commits should be marked as "success" only if all tests pass
      And commits should be marked as "failure" and developers notified if any test fails
      And sensitive information like Discord Webhook URLs should be managed securely using GitHub Secrets, not hardcoded in source code
