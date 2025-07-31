Feature: Detect page structure change
  Background:
    Given the monitor target URL is set
    And a Discord Webhook URL is configured

  Scenario: HTML structure changed
    Given the Rakuten site has undergone a redesign and the HTML structure has changed
      And the tool can no longer correctly parse product information
    When the monitor checks the page
    Then the parsing failure should be logged
      And a Discord message "警告: ページの構造が変更された可能性があります。ツールのメンテナンスが必要です。" should be sent
