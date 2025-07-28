#!/usr/bin/env python
"""Discord Error Handler for logging ERROR+ messages to Discord alerts."""
import logging
import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


class DiscordErrorHandler(logging.Handler):
    """Logging handler that sends ERROR and above messages to Discord."""
    
    def __init__(self, level=logging.ERROR):
        """
        Initialize Discord error handler.
        
        Args:
            level: Logging level (default: logging.ERROR)
        """
        super().__init__(level=level)
        self.webhook_url = os.getenv('ALERT_WEBHOOK_URL')
        if not self.webhook_url:
            print("WARN: No ALERT_WEBHOOK_URL provided for Discord alerts")
    
    def emit(self, record):
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
                color = 0xff0000  # Red
                emoji = "🚨"
                title = "CRITICAL ERROR"
            elif record.levelno >= logging.ERROR:
                color = 0xff6600  # Orange
                emoji = "❌"
                title = "ERROR"
            else:
                color = 0xffaa00  # Yellow
                emoji = "⚠️"
                title = "WARNING"
            
            # Create Discord embed
            embed = {
                "title": f"{emoji} {title}",
                "description": f"```\n{message}\n```",
                "color": color,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "fields": [
                    {
                        "name": "Logger",
                        "value": record.name,
                        "inline": True
                    },
                    {
                        "name": "Level",
                        "value": record.levelname,
                        "inline": True
                    },
                    {
                        "name": "Module",
                        "value": f"{record.filename}:{record.lineno}",
                        "inline": True
                    }
                ]
            }
            
            # Add exception info if available
            if record.exc_info:
                embed["fields"].append({
                    "name": "Exception",
                    "value": f"```\n{self.formatException(record.exc_info)}\n```",
                    "inline": False
                })
            
            # Send to Discord
            payload = {
                "embeds": [embed]
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            # Discord webhooks return 204 on success
            if response.status_code != 204:
                print(f"WARN: failed to send alert - HTTP {response.status_code}")
                
        except Exception:
            # Don't let logging errors break the application
            print("WARN: failed to send alert")


def setup_discord_error_logging(logger_name=None):
    """
    Set up Discord error logging for ERROR+ messages.
    
    Args:
        logger_name (str, optional): Name of the logger. If None, uses root logger.
        
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(logger_name)
    
    # Don't add duplicate handlers
    if any(isinstance(h, DiscordErrorHandler) for h in logger.handlers):
        return logger
    
    # Add Discord error handler
    discord_handler = DiscordErrorHandler(level=logging.ERROR)
    discord_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    )
    logger.addHandler(discord_handler)
    
    return logger


def test_error_alert():
    """Send a test error alert to verify Discord integration."""
    logger = setup_discord_error_logging('test_logger')
    logger.setLevel(logging.DEBUG)  # Ensure all levels are captured
    logger.error("Test error alert from Rakuten monitoring system")
    print("Test error alert sent (if ALERT_WEBHOOK_URL is configured)")


if __name__ == "__main__":
    test_error_alert()