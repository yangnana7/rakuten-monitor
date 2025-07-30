"""
Settings module for environment variable management.
"""

import os
import sys
import logging
from typing import Any

log = logging.getLogger(__name__)


class _MISSING:
    """Sentinel class for missing values."""

    pass


def getenv_or_exit(key: str, default: Any = _MISSING) -> str:
    """
    Get environment variable or exit with error.

    Args:
        key: Environment variable name
        default: Default value if provided (avoids exit)

    Returns:
        str: Environment variable value

    Raises:
        SystemExit: If variable is not set and no default provided
    """
    value = os.getenv(key)
    if not value:
        if default is not _MISSING:
            return default
        log.error("%s is not set; aborting.", key)
        sys.exit(1)
    return value


def get_webhook_url() -> str:
    """Get Discord webhook URL from environment."""
    return getenv_or_exit("DISCORD_WEBHOOK_URL")


def get_alert_webhook_url() -> str:
    """Get alert webhook URL from environment."""
    return getenv_or_exit("ALERT_WEBHOOK_URL", "https://discord.com/api/webhooks/dummy")


def get_list_url() -> str:
    """Get target list URL from environment."""
    return getenv_or_exit(
        "LIST_URL", "https://item.rakuten.co.jp/auc-p-entamestore/c/0000000174/?s=4"
    )


def get_database_url() -> str:
    """Get database URL from environment."""
    return getenv_or_exit("DATABASE_URL", "rakuten_monitor.db")
