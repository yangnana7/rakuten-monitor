import pytest
from pytest_bdd import scenarios, given, then

scenarios("../../features/01_new_product.feature")


@given("a product that did not exist in the previous run now appears on the page")
def new_product_appears():
    pytest.skip("Step implementation pending")


@given('the new product is "in stock"')
def new_product_in_stock():
    pytest.skip("Step implementation pending")


@then('a Discord message "【新商品】<name> が入荷しました！ <price> <url>" is sent')
def discord_new_product_message_sent():
    pytest.skip("Step implementation pending")
