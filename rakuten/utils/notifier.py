"""
Unified notifier using DiscordClient internally.
"""

import os
from typing import Dict

from dotenv import load_dotenv

from ..discord_client import DiscordClient, DiscordSendError

load_dotenv()


def send_notification(item_dict: Dict[str, str]) -> bool:
    """
    Discord Webhookに商品通知を送信する (DiscordClient経由).

    Args:
        item_dict (Dict[str, str]): 商品情報辞書
            - item_code: 商品コード
            - title: 商品タイトル
            - status: 商品ステータス (NEW/RESALE/UNCHANGED)

    Returns:
        bool: 送信成功時True、失敗時False
    """
    try:
        # 必須フィールドのチェック
        required_fields = ["item_code", "title", "status"]
        for field in required_fields:
            if field not in item_dict:
                return False

        status = item_dict["status"]

        # UNCHANGEDの場合は通知しない（成功として扱う）
        if status == "UNCHANGED":
            return True

        # ステータスに応じたメッセージ設定
        if status == "NEW":
            title = "🆕 新商品発見"
            color = 0x00FF00  # Green
        elif status == "RESALE":
            title = "🔄 再販商品発見"
            color = 0xFF9900  # Orange
        else:
            # 未知のステータスの場合はデフォルト
            title = "📦 商品更新"
            color = 0x0099FF  # Blue

        # Discord client経由で送信
        webhook_url = _get_webhook_url()
        client = DiscordClient(webhook_url, timeout=10.0)

        description = (
            f"**{item_dict['title']}**\n\n商品コード: `{item_dict['item_code']}`"
        )

        client.send_embed(
            title=title,
            description=description,
            color=color,
        )

        return True

    except DiscordSendError:
        # Discord送信エラー
        return False
    except Exception:
        # その他の例外
        return False


def _get_webhook_url() -> str:
    """
    Discord Webhook URLを取得する。

    Returns:
        str: Webhook URL
    """
    return os.getenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/dummy")
