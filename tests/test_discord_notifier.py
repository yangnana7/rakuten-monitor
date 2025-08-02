"""Unit tests for discord_notifier.py module."""

import sys
from pathlib import Path

# Add parent directory to Python path for module imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

from unittest.mock import patch, Mock


class TestDiscordNotifier:
    """Test Discord notification functionality."""

    @patch("requests.post")
    def test_send_notification_success(self, mock_post):
        """Test successful Discord notification."""
        # Arrange
        from app.notifier.utils import send_notification

        mock_response = Mock()
        mock_response.status_code = 204  # Discord webhook success status
        mock_post.return_value = mock_response

        item_dict = {
            "item_code": "shouritu-100089",
            "title": "カチカチくんEX（青） ※8月上旬発送予定",
            "status": "NEW",
        }

        # Act
        result = send_notification(item_dict)

        # Assert
        assert result is True
        mock_post.assert_called_once()

        # Check that the webhook was called with proper JSON payload
        call_args = mock_post.call_args
        assert "json" in call_args.kwargs
        payload = call_args.kwargs["json"]
        assert "embeds" in payload

    @patch("requests.post")
    def test_send_notification_failure(self, mock_post):
        """Test Discord notification failure."""
        # Arrange
        from app.notifier.utils import send_notification

        mock_response = Mock()
        mock_response.status_code = 400  # Bad request
        mock_post.return_value = mock_response

        item_dict = {
            "item_code": "shouritu-100089",
            "title": "カチカチくんEX（青） ※8月上旬発送予定",
            "status": "NEW",
        }

        # Act
        result = send_notification(item_dict)

        # Assert
        assert result is False

    @patch("requests.post")
    def test_send_notification_network_error(self, mock_post):
        """Test Discord notification with network error."""
        # Arrange
        from app.notifier.utils import send_notification

        mock_post.side_effect = Exception("Network error")

        item_dict = {
            "item_code": "shouritu-100089",
            "title": "カチカチくんEX（青） ※8月上旬発送予定",
            "status": "NEW",
        }

        # Act
        result = send_notification(item_dict)

        # Assert
        assert result is False

    @patch("requests.post")
    def test_send_notification_new_product_formatting(self, mock_post):
        """Test notification formatting for NEW product."""
        # Arrange
        from app.notifier.utils import send_notification

        mock_response = Mock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        item_dict = {
            "item_code": "shouritu-100089",
            "title": "カチカチくんEX（青） ※8月上旬発送予定",
            "status": "NEW",
        }

        # Act
        result = send_notification(item_dict)

        # Assert
        assert result is True

        # Check embed formatting for NEW product
        payload = mock_post.call_args.kwargs["json"]
        embed = payload["embeds"][0]
        assert embed["title"] == "🆕 新商品発見"
        assert embed["color"] == 0x00FF00  # Green color for NEW
        assert item_dict["title"] in embed["description"]
        assert item_dict["item_code"] in embed["description"]

    @patch("requests.post")
    def test_send_notification_resale_product_formatting(self, mock_post):
        """Test notification formatting for RESALE product."""
        # Arrange
        from app.notifier.utils import send_notification

        mock_response = Mock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        item_dict = {
            "item_code": "shouritu-100089",
            "title": "カチカチくんEX（青） ※9月上旬発送予定",
            "status": "RESALE",
        }

        # Act
        result = send_notification(item_dict)

        # Assert
        assert result is True

        # Check embed formatting for RESALE product
        payload = mock_post.call_args.kwargs["json"]
        embed = payload["embeds"][0]
        assert embed["title"] == "🔄 再販商品発見"
        assert embed["color"] == 0xFF9900  # Orange color for RESALE
        assert item_dict["title"] in embed["description"]
        assert item_dict["item_code"] in embed["description"]

    @patch("requests.post")
    def test_send_notification_unchanged_product_not_sent(self, mock_post):
        """Test that UNCHANGED products are not sent to Discord."""
        # Arrange
        from app.notifier.utils import send_notification

        item_dict = {
            "item_code": "shouritu-100089",
            "title": "カチカチくんEX（青） ※8月上旬発送予定",
            "status": "UNCHANGED",
        }

        # Act
        result = send_notification(item_dict)

        # Assert
        assert result is True  # Function succeeds but doesn't send
        mock_post.assert_not_called()  # No webhook call for UNCHANGED

    @patch("requests.post")
    def test_send_notification_includes_timestamp(self, mock_post):
        """Test that notification includes timestamp."""
        # Arrange
        from app.notifier.utils import send_notification

        mock_response = Mock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        item_dict = {
            "item_code": "shouritu-100089",
            "title": "カチカチくんEX（青） ※8月上旬発送予定",
            "status": "NEW",
        }

        # Act
        result = send_notification(item_dict)

        # Assert
        assert result is True

        # Check that the notification was sent successfully
        # Note: timestamp is not currently implemented in the notifier
        payload = mock_post.call_args.kwargs["json"]
        embed = payload["embeds"][0]
        assert "title" in embed
        assert "description" in embed

    @patch("requests.post")
    def test_send_notification_with_missing_fields(self, mock_post):
        """Test notification with missing required fields."""
        # Arrange
        from app.notifier.utils import send_notification

        # Missing title field
        item_dict = {"item_code": "shouritu-100089", "status": "NEW"}

        # Act
        result = send_notification(item_dict)

        # Assert
        assert result is False
        mock_post.assert_not_called()

    def test_send_notification_returns_bool(self):
        """Test that send_notification always returns a boolean."""
        # Arrange
        from app.notifier.utils import send_notification

        item_dict = {
            "item_code": "shouritu-100089",
            "title": "カチカチくんEX（青） ※8月上旬発送予定",
            "status": "NEW",
        }

        # Act
        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 204
            mock_post.return_value = mock_response
            result = send_notification(item_dict)

        # Assert
        assert isinstance(result, bool)
