"""
Error handler decorator for alerting on exceptions.
"""

import functools
import sys
import traceback
from typing import Any, Callable

from .discord_client import DiscordClient, DiscordSendError


def alert_on_exception(
    client: DiscordClient, channel: str = "#alerts"
) -> Callable[[Callable], Callable]:
    """
    Decorator to catch exceptions and send alerts to Discord.

    Args:
        client: DiscordClient instance for sending alerts
        channel: Channel name for the alert (included in title)

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Get stack trace
                tb_str = traceback.format_exc()

                # Create alert message
                title = f"Exception in {func.__name__} {channel}"
                description = f"**Error:** {type(e).__name__}: {str(e)}\n\n**Function:** `{func.__name__}`"

                # Add stack trace as a field (truncate if too long)
                fields = {}
                if len(tb_str) > 1000:
                    fields["Stack Trace"] = tb_str[:997] + "..."
                else:
                    fields["Stack Trace"] = tb_str

                try:
                    client.send_embed(
                        title=title,
                        description=description,
                        color=0xFF0000,  # Red color for errors
                        fields=fields,
                    )
                except DiscordSendError as discord_err:
                    # If Discord sending fails, only log to stderr
                    print(
                        f"Failed to send Discord alert: {discord_err}", file=sys.stderr
                    )
                except Exception as discord_exc:
                    # Catch any other Discord-related errors
                    print(
                        f"Unexpected error sending Discord alert: {discord_exc}",
                        file=sys.stderr,
                    )

                # Re-raise the original exception
                raise

        return wrapper

    return decorator
