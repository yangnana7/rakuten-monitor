import pytest
from pytest_bdd import scenarios, given, then

scenarios("../../features/02_restock.feature")


@given('a product that was "sold out" in the previous run')
def product_was_sold_out():
    pytest.skip("Step implementation pending")


@given('the product is now "in stock"')
def product_now_in_stock():
    pytest.skip("Step implementation pending")


@then('a Discord message "【再販】<name>の在庫が復活しました！ <price> <url>" is sent')
def discord_restock_message_sent():
    pytest.skip("Step implementation pending")
