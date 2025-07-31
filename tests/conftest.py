"""
Pytest configuration and fixtures for the rakuten monitor tests.
"""

import pytest
import tempfile
import os
from pytest_httpserver import HTTPServer

# Register BDD step definitions plugin
pytest_plugins = ["tests.bdd_steps.common_steps"]


@pytest.fixture(autouse=True)
def set_test_env_vars(monkeypatch):
    """
    Automatically set dummy environment variables for all tests.
    """
    # Set dummy webhook URLs
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "http://dummy.local/webhook")
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "http://dummy.local/alert")

    # Set test database URL
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test_rakuten_monitor.db")

    # Set test list URL
    monkeypatch.setenv("LIST_URL", "https://test.example.com/products")


@pytest.fixture
def temp_db():
    """
    Create a temporary database file for testing.
    """
    temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = temp_db.name
    temp_db.close()

    yield db_path

    # Cleanup
    try:
        os.unlink(db_path)
    except (PermissionError, OSError):
        pass


@pytest.fixture
def sample_item_data():
    """
    Sample item data for testing.
    """
    return {
        "item_code": "test-item-001",
        "title": "テスト商品 ※8月上旬発送予定",
        "status": "NEW",
        "price": 1000,
        "url": "https://example.com/test-item-001",
    }


@pytest.fixture
def httpserver():
    """
    HTTPServer fixture for BDD tests.
    """
    server = HTTPServer(host="127.0.0.1", port=0)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def dummy_messages(monkeypatch):
    """
    Fixture to capture Discord messages for BDD tests.
    """
    sent = []

    def mock_send_embed(self, title, description, **kwargs):
        sent.append(f"{title}: {description}")

    monkeypatch.setattr(
        "rakuten.discord_client.DiscordClient.send_embed", mock_send_embed
    )
    return sent
