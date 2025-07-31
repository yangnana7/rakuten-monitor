@bdd
Feature: Safe development workflow and quality assurance
  As a developer using AI coding assistance
  I want automated testing through GitHub Actions
  So that code changes are validated in a clean environment before deployment

  Background:
    Given the development workflow uses AI (Claude Code) for code generation
    And the production environment is Ubuntu server
    And the development environment is Windows

  Scenario: Automated testing via GitHub Actions
    Given a developer instructs AI to generate or modify code
    And the resulting code is pushed to GitHub
    When GitHub Actions workflow is automatically triggered
    Then all tests should be executed in a clean virtual environment similar to Ubuntu production
    And only if all tests pass should the code be considered "likely to work in production"
    And monitoring target URLs and time windows should be changed by modifying config files, not source code
    And sensitive information like Discord webhook URLs should not be in source code
    And sensitive information should be tested via GitHub Secrets and loaded from environment variables in production
