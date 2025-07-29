#!/usr/bin/env python
"""Error handler with Discord alert functionality."""
import logging
import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


class DiscordAlertHandler(logging.Handler):
    """Logging handler that sends ERROR and above messages to Discord."""

    def __init__(self, webhook_url: str = None):
        """
        Initialize Discord alert handler.

        Args:
            webhook_url (str, optional): Discord webhook URL. If not provided,
                                       will use ALERT_WEBHOOK_URL from environment.
        """
        super().__init__(level=logging.ERROR)
        self.webhook_url = webhook_url or os.getenv("ALERT_WEBHOOK_URL")
        if not self.webhook_url:
            logging.warning("No ALERT_WEBHOOK_URL provided for Discord alerts")

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record by sending it to Discord.

        Args:
            record: The log record to send
        """
        if not self.webhook_url:
            return

        try:
            # Format the log message
            message = self.format(record)

            # Determine embed color based on log level
            if record.levelno >= logging.CRITICAL:
                color = 0xFF0000  # Red
                emoji = "🚨"
                title = "CRITICAL ERROR"
            elif record.levelno >= logging.ERROR:
                color = 0xFF6600  # Orange
                emoji = "❌"
                title = "ERROR"
            else:
                color = 0xFFAA00  # Yellow
                emoji = "⚠️"
                title = "WARNING"

            # Create Discord embed
            embed = {
                "title": f"{emoji} {title}",
                "description": f"```\n{message}\n```",
                "color": color,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "fields": [
                    {"name": "Logger", "value": record.name, "inline": True},
                    {"name": "Level", "value": record.levelname, "inline": True},
                    {
                        "name": "Module",
                        "value": f"{record.filename}:{record.lineno}",
                        "inline": True,
                    },
                ],
            }

            # Add exception info if available
            if record.exc_info:
                embed["fields"].append(
                    {
                        "name": "Exception",
                        "value": f"```\n{self.formatException(record.exc_info)}\n```",
                        "inline": False,
                    }
                )

            # Send to Discord
            payload = {"embeds": [embed]}

            response = requests.post(self.webhook_url, json=payload, timeout=10)

            # Discord webhooks return 204 on success
            if response.status_code != 204:
                logging.warning(
                    f"Failed to send Discord alert: HTTP {response.status_code}"
                )

        except Exception as e:
            # Don't let logging errors break the application
            logging.warning(f"Failed to send Discord alert: {e}")


def setup_error_logging(logger_name: str = None) -> logging.Logger:
    """
    Set up error logging with Discord alerts.

    Args:
        logger_name (str, optional): Name of the logger. If None, uses root logger.

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(logger_name)

    # Don't add duplicate handlers
    if any(isinstance(h, DiscordAlertHandler) for h in logger.handlers):
        return logger

    # Add Discord alert handler
    discord_handler = DiscordAlertHandler()
    discord_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(discord_handler)

    return logger


def send_test_alert():
    """Send a test alert to verify Discord integration."""
    logger = setup_error_logging("test_logger")
    logger.error("This is a test error alert from the Rakuten monitoring system")
    print("Test alert sent (if ALERT_WEBHOOK_URL is configured)")


if __name__ == "__main__":
    send_test_alert()
