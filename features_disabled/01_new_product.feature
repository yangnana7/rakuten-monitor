Feature: Detect new product
  Background:
    Given the monitor target URL is set
    And a Discord Webhook URL is configured
    And previous run data (item list & stock state) exists

  Scenario: New product added
    Given a product that did not exist in the previous run now appears on the page
      And the new product is "in stock"
    When the monitor checks the page
    Then the tool should collect the product name, price and URL
      And a Discord message "【新商品】<name> が入荷しました！ <price> <url>" is sent
