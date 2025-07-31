Feature: Detect restock
  Background:
    Given the monitor target URL is set
    And a Discord Webhook URL is configured
    And previous run data (item list & stock state) exists

  Scenario: Sold-out product restocked
    Given a product that was "sold out" in the previous run
      And the product is now "in stock"
    When the monitor checks the page
    Then the tool should collect the product name, price and URL
      And a Discord message "【再販】<name>の在庫が復活しました！ <price> <url>" is sent
