import pytest
from pytest_bdd import scenarios, given, then

scenarios("../../features/05_structure_change.feature")


@given("the Rakuten site has undergone a redesign and the HTML structure has changed")
def rakuten_structure_changed():
    pytest.skip("Step implementation pending")


@given("the tool can no longer correctly parse product information")
def tool_cannot_parse():
    pytest.skip("Step implementation pending")


@then("the parsing failure should be logged")
def parsing_failure_logged():
    pytest.skip("Step implementation pending")


@then(
    'a Discord message "警告: ページの構造が変更された可能性があります。ツールのメンテナンスが必要です。" should be sent'
)
def discord_structure_warning_sent():
    pytest.skip("Step implementation pending")
