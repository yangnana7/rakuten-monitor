import pytest
from pytest_bdd import scenarios, given, then

scenarios("../../features/03_no_change.feature")


@given(
    "the product lineup and all product stock states are identical to the previous run"
)
def product_lineup_identical():
    pytest.skip("Step implementation pending")


@then("no action should be taken")
def no_action_taken():
    pytest.skip("Step implementation pending")


@then("no Discord notification should be sent")
def no_discord_notification():
    pytest.skip("Step implementation pending")
