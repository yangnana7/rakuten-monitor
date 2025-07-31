Feature: Handle unreachable page
  Background:
    Given the monitor target URL is set
    And a Discord Webhook URL is configured

  Scenario: Target URL unreachable
    Given the Rakuten server is under maintenance or network issues prevent access to the target URL
    When the monitor attempts to check the page
    Then the error should be logged
      And a Discord message "エラー: 楽天市場のページにアクセスできませんでした。" should be sent
