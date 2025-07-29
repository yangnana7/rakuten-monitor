"""
Tests for Discord client.
"""

import pytest
import requests
import requests_mock

from rakuten.discord_client import DiscordClient, DiscordSendError


class TestDiscordClient:
    """Test cases for DiscordClient."""

    def setup_method(self):
        """Setup method for each test."""
        self.webhook_url = "https://discord.com/api/webhooks/123/test"
        self.client = DiscordClient(self.webhook_url, timeout=2.0)

    def test_send_embed_success(self):
        """Test successful embed sending."""
        with requests_mock.Mocker() as m:
            m.post(self.webhook_url, status_code=204)

            # Should not raise any exception
            self.client.send_embed(
                title="Test Title",
                description="Test Description",
                url="https://example.com",
                color=0xFF0000,
                fields={"Status": "New", "Price": "¥1000"},
            )

            # Verify the request was made with correct payload
            assert m.call_count == 1
            request = m.request_history[0]
            payload = request.json()

            assert "embeds" in payload
            embed = payload["embeds"][0]
            assert embed["title"] == "Test Title"
            assert embed["description"] == "Test Description"
            assert embed["url"] == "https://example.com"
            assert embed["color"] == 0xFF0000
            assert len(embed["fields"]) == 2
            assert embed["fields"][0]["name"] == "Status"
            assert embed["fields"][0]["value"] == "New"

    def test_send_embed_minimal(self):
        """Test sending embed with minimal parameters."""
        with requests_mock.Mocker() as m:
            m.post(self.webhook_url, status_code=200)

            self.client.send_embed(title="Title", description="Description")

            assert m.call_count == 1
            request = m.request_history[0]
            payload = request.json()

            embed = payload["embeds"][0]
            assert embed["title"] == "Title"
            assert embed["description"] == "Description"
            assert embed["color"] == 0xF5A623  # default color
            assert "url" not in embed
            assert "fields" not in embed

    def test_send_embed_http_error(self):
        """Test DiscordSendError is raised on HTTP error."""
        with requests_mock.Mocker() as m:
            m.post(self.webhook_url, status_code=400, text="Bad Request")

            with pytest.raises(DiscordSendError) as exc_info:
                self.client.send_embed("Title", "Description")

            assert "400" in str(exc_info.value)
            assert "Bad Request" in str(exc_info.value)

    def test_send_embed_network_error(self):
        """Test DiscordSendError is raised on network error."""
        with requests_mock.Mocker() as m:
            m.post(self.webhook_url, exc=requests.ConnectionError("Connection failed"))

            with pytest.raises(DiscordSendError) as exc_info:
                self.client.send_embed("Title", "Description")

            assert "Connection failed" in str(exc_info.value)

    def test_send_embed_timeout_error(self):
        """Test DiscordSendError is raised on timeout."""
        with requests_mock.Mocker() as m:
            m.post(self.webhook_url, exc=requests.Timeout("Timeout"))

            with pytest.raises(DiscordSendError) as exc_info:
                self.client.send_embed("Title", "Description")

            assert "Timeout" in str(exc_info.value)

    def test_initialization(self):
        """Test client initialization."""
        client = DiscordClient("https://test.com", timeout=5.0)
        assert client.webhook_url == "https://test.com"
        assert client.timeout == 5.0

        # Test default timeout
        client_default = DiscordClient("https://test.com")
        assert client_default.timeout == 2.0
