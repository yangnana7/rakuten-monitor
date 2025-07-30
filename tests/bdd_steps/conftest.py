import pytest
from pytest_bdd import given, when, then


@given("the monitor target URL is set")
def monitor_url_set():
    # Environment variable is already set by parent conftest.py
    pass


@given("a Discord Webhook URL is configured")
def discord_webhook_configured():
    # Environment variable is already set by parent conftest.py
    pass


@given("previous run data (item list & stock state) exists")
def previous_run_data_exists():
    pytest.skip("Step implementation pending")


@when("the monitor checks the page")
def monitor_checks_page():
    pytest.skip("Step implementation pending")


@then("the tool should collect the product name, price and URL")
def tool_collects_product_info():
    pytest.skip("Step implementation pending")
