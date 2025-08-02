"""
Discord client for sending webhook messages.
"""

from typing import Dict, Optional

import requests


class DiscordSendError(Exception):
    """Exception raised when Discord webhook send fails."""

    pass


class DiscordPostError(Exception):
    """Exception raised when Discord POST request fails."""

    pass


class DiscordClient:
    """Discord webhook client for sending embed messages."""

    def __init__(self, webhook_url: str, timeout: float = 2.0) -> None:
        """
        Initialize Discord client.

        Args:
            webhook_url: Discord webhook URL
            timeout: Request timeout in seconds
        """
        self.webhook_url = webhook_url
        self.timeout = timeout

    def send_embed(
        self,
        title: str,
        description: str,
        url: Optional[str] = None,
        color: int = 0xF5A623,
        fields: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Send embed message to Discord.

        Args:
            title: Embed title
            description: Embed description
            url: Optional URL for the embed
            color: Embed color (default: orange)
            fields: Optional dictionary of field name -> value pairs

        Raises:
            DiscordSendError: If webhook request fails
        """
        embed = {
            "title": title,
            "description": description,
            "color": color,
        }

        if url:
            embed["url"] = url

        if fields:
            embed["fields"] = [
                {"name": name, "value": value, "inline": True}
                for name, value in fields.items()
            ]

        payload = {"embeds": [embed]}

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )

            if not (200 <= response.status_code < 300):
                raise DiscordPostError(
                    f"Discord webhook failed with status {response.status_code}: {response.text}"
                )

        except requests.RequestException as e:
            raise DiscordPostError(f"Failed to send Discord webhook: {e}") from e
