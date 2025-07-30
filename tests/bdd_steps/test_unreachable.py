import pytest
from pytest_bdd import scenarios, given, when, then

scenarios("../../features/04_unreachable.feature")


@given(
    "the Rakuten server is under maintenance or network issues prevent access to the target URL"
)
def rakuten_server_unreachable():
    pytest.skip("Step implementation pending")


@when("the monitor attempts to check the page")
def monitor_attempts_check():
    pytest.skip("Step implementation pending")


@then("the error should be logged")
def error_logged():
    pytest.skip("Step implementation pending")


@then(
    'a Discord message "エラー: 楽天市場のページにアクセスできませんでした。" should be sent'
)
def discord_error_message_sent():
    pytest.skip("Step implementation pending")
