"""
Tests for error handler decorator.
"""

import pytest
from unittest.mock import MagicMock, patch
import sys
from io import StringIO

from rakuten.error_handler import alert_on_exception
from rakuten.discord_client import DiscordClient, DiscordSendError


class TestErrorHandler:
    """Test cases for error handler decorator."""

    def setup_method(self):
        """Setup method for each test."""
        self.mock_client = MagicMock(spec=DiscordClient)
        self.decorator = alert_on_exception(self.mock_client, "#test-alerts")

    def test_alert_on_exception_normal_execution(self):
        """Test decorator doesn't interfere with normal execution."""

        @self.decorator
        def test_function(x, y):
            return x + y

        result = test_function(1, 2)
        assert result == 3
        # Should not call Discord client for successful execution
        self.mock_client.send_embed.assert_not_called()

    def test_alert_on_exception_catches_and_alerts(self):
        """Test decorator catches exceptions and sends alerts."""

        @self.decorator
        def failing_function():
            raise ValueError("Test error message")

        with pytest.raises(ValueError, match="Test error message"):
            failing_function()

        # Verify Discord client was called
        self.mock_client.send_embed.assert_called_once()
        call_args = self.mock_client.send_embed.call_args

        # Check the arguments passed to send_embed
        assert "Exception in failing_function #test-alerts" == call_args.kwargs["title"]
        assert "ValueError: Test error message" in call_args.kwargs["description"]
        assert "failing_function" in call_args.kwargs["description"]
        assert call_args.kwargs["color"] == 0xFF0000  # Red color
        assert "Stack Trace" in call_args.kwargs["fields"]
        assert "ValueError: Test error message" in call_args.kwargs["fields"]["Stack Trace"]

    def test_alert_on_exception_truncates_long_stacktrace(self):
        """Test that long stack traces are truncated."""

        @self.decorator
        def failing_function():
            raise RuntimeError("Error with very long stack trace")

        # Mock traceback.format_exc to return a long string
        with patch("rakuten.error_handler.traceback.format_exc") as mock_traceback:
            long_trace = "x" * 1500  # Longer than 1000 characters
            mock_traceback.return_value = long_trace

            with pytest.raises(RuntimeError):
                failing_function()

            # Verify stack trace was truncated
            call_args = self.mock_client.send_embed.call_args
            stack_trace_field = call_args.kwargs["fields"]["Stack Trace"]
            assert len(stack_trace_field) == 1000  # 997 + "..."
            assert stack_trace_field.endswith("...")

    def test_alert_on_exception_handles_discord_send_error(self):
        """Test decorator handles DiscordSendError gracefully."""
        # Setup mock to raise DiscordSendError
        self.mock_client.send_embed.side_effect = DiscordSendError("Discord failed")

        @self.decorator
        def failing_function():
            raise ValueError("Test error")

        # Capture stderr
        captured_stderr = StringIO()
        with patch.object(sys, "stderr", captured_stderr):
            with pytest.raises(ValueError):
                failing_function()

        # Verify error was logged to stderr
        stderr_output = captured_stderr.getvalue()
        assert "Failed to send Discord alert: Discord failed" in stderr_output

    def test_alert_on_exception_handles_unexpected_discord_error(self):
        """Test decorator handles unexpected Discord errors gracefully."""
        # Setup mock to raise unexpected error
        self.mock_client.send_embed.side_effect = Exception("Unexpected Discord error")

        @self.decorator
        def failing_function():
            raise ValueError("Test error")

        # Capture stderr
        captured_stderr = StringIO()
        with patch.object(sys, "stderr", captured_stderr):
            with pytest.raises(ValueError):
                failing_function()

        # Verify error was logged to stderr
        stderr_output = captured_stderr.getvalue()
        assert "Unexpected error sending Discord alert: Unexpected Discord error" in stderr_output

    def test_alert_on_exception_preserves_function_metadata(self):
        """Test decorator preserves original function metadata."""

        @self.decorator
        def test_function():
            """Test function docstring."""
            pass

        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "Test function docstring."

    def test_alert_on_exception_with_function_arguments(self):
        """Test decorator works with functions that have arguments."""

        @self.decorator
        def function_with_args(a, b, c=None, *args, **kwargs):
            if a == "fail":
                raise TypeError("Function argument error")
            return f"{a}-{b}-{c}"

        # Test normal execution
        result = function_with_args("test", "value", c="optional")
        assert result == "test-value-optional"
        self.mock_client.send_embed.assert_not_called()

        # Test with exception
        with pytest.raises(TypeError):
            function_with_args("fail", "value", extra="kwarg")

        # Verify alert was sent
        self.mock_client.send_embed.assert_called_once()
        call_args = self.mock_client.send_embed.call_args
        assert "function_with_args" in call_args.kwargs["title"]

    def test_default_channel_parameter(self):
        """Test decorator uses default channel when not specified."""
        decorator_default = alert_on_exception(self.mock_client)

        @decorator_default
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()

        # Verify default channel is used
        call_args = self.mock_client.send_embed.call_args
        assert "#alerts" in call_args.kwargs["title"]
