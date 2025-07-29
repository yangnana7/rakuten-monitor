#!/usr/bin/env python3
"""
Discord Webhook 通知機能
"""

import requests
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class DiscordNotifier:
    def __init__(
        self, webhook_url: Optional[str] = None, alert_webhook_url: Optional[str] = None
    ):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        self.alert_webhook_url = alert_webhook_url or os.getenv(
            "DISCORD_ALERT_WEBHOOK_URL"
        )
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured")

    def create_embed(self, change: Dict[str, Any]) -> Dict[str, Any]:
        """変更情報からDiscord埋め込みを作成"""
        change_type = change["type"]
        title = change.get("title", "Unknown Product")
        url = change.get("url", "")
        price = change.get("price")

        # タイプごとのアイコンと色
        type_config = {
            "NEW": {"emoji": "🆕", "color": 0x00FF00, "title_prefix": "NEW"},
            "RESTOCK": {"emoji": "🔄", "color": 0x0099FF, "title_prefix": "RESTOCK"},
            "TITLE_UPDATE": {
                "emoji": "📝",
                "color": 0xFFAA00,
                "title_prefix": "TITLE UPDATE",
            },
            "PRICE_UPDATE": {
                "emoji": "💰",
                "color": 0xFF6600,
                "title_prefix": "PRICE UPDATE",
            },
            "SOLDOUT": {"emoji": "❌", "color": 0xFF0000, "title_prefix": "SOLD OUT"},
        }

        config = type_config.get(change_type, type_config["NEW"])

        embed = {
            "title": f"{config['emoji']} {config['title_prefix']}: {title[:100]}",
            "url": url,
            "color": config["color"],
            "timestamp": datetime.now().isoformat(),
            "fields": [],
        }

        # 価格情報
        if price:
            embed["fields"].append(
                {"name": "価格", "value": f"{price:,}円", "inline": True}
            )

        # 在庫状況
        if "in_stock" in change:
            stock_status = "○" if change["in_stock"] else "×"
            embed["fields"].append(
                {"name": "在庫", "value": stock_status, "inline": True}
            )

        # タイトル変更の場合は詳細情報
        if change_type == "TITLE_UPDATE":
            embed["fields"].extend(
                [
                    {
                        "name": "旧タイトル",
                        "value": change.get("old_title", "Unknown")[:1000],
                        "inline": False,
                    },
                    {
                        "name": "新タイトル",
                        "value": change.get("new_title", "Unknown")[:1000],
                        "inline": False,
                    },
                ]
            )
        # 価格変更の場合は詳細情報
        elif change_type == "PRICE_UPDATE":
            old_price = change.get("old_price")
            new_price = change.get("new_price")
            if old_price is not None and new_price is not None:
                price_diff = new_price - old_price
                diff_text = (
                    f"+{price_diff:,}円" if price_diff > 0 else f"{price_diff:,}円"
                )
                embed["fields"].extend(
                    [
                        {"name": "旧価格", "value": f"{old_price:,}円", "inline": True},
                        {"name": "新価格", "value": f"{new_price:,}円", "inline": True},
                        {"name": "価格差", "value": diff_text, "inline": True},
                    ]
                )

        return embed

    def _get_type_config(self, change_type: str) -> Dict[str, Any]:
        """変更タイプの設定を取得"""
        type_config = {
            "NEW": {"emoji": "🆕", "color": 0x00FF00, "title_prefix": "NEW"},
            "RESTOCK": {"emoji": "🎉", "color": 0x0099FF, "title_prefix": "在庫復活"},
            "TITLE_UPDATE": {
                "emoji": "📝",
                "color": 0xFFAA00,
                "title_prefix": "タイトル変更",
            },
            "PRICE_UPDATE": {
                "emoji": "💰",
                "color": 0xFF6600,
                "title_prefix": "価格更新",
            },
            "SOLDOUT": {"emoji": "❌", "color": 0xFF0000, "title_prefix": "売り切れ"},
        }
        return type_config.get(change_type, type_config["NEW"])

    def send_notification(self, changes: List[Dict[str, Any]]) -> bool:
        """変更通知をDiscordに送信（改善版）"""
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured, skipping notification")
            return False

        if not changes:
            logger.info("No changes to notify")
            return True

        try:
            # 変更タイプごとにグループ化
            change_groups = {}
            for change in changes:
                change_type = change["type"]
                if change_type not in change_groups:
                    change_groups[change_type] = []
                change_groups[change_type].append(change)

            # 日本語ローカライゼーション
            type_names = {
                "NEW": "新商品追加",
                "RESTOCK": "在庫復活",
                "TITLE_UPDATE": "タイトル変更",
                "PRICE_UPDATE": "価格更新",
                "SOLDOUT": "売り切れ",
            }

            embeds = []
            total_changes = len(changes)

            # 最大10件のembedに制限
            if total_changes <= 10:
                # 通常の個別embed表示
                for change in changes:
                    embeds.append(self.create_embed(change))
            else:
                # 多数の変更がある場合はサマリー表示
                summary_embed = {
                    "title": f"📊 商品変更サマリー（合計 {total_changes} 件）",
                    "color": 0x5865F2,
                    "timestamp": datetime.now().isoformat(),
                    "fields": [],
                }

                for change_type, group_changes in change_groups.items():
                    type_name = type_names.get(change_type, change_type)
                    count = len(group_changes)
                    config = self._get_type_config(change_type)

                    summary_embed["fields"].append(
                        {
                            "name": f"{config['emoji']} {type_name}",
                            "value": f"{count} 件",
                            "inline": True,
                        }
                    )

                embeds.append(summary_embed)

                # 重要度の高い変更（NEW、RESTOCK）は個別表示
                important_changes = []
                for change_type in ["NEW", "RESTOCK"]:
                    if change_type in change_groups:
                        important_changes.extend(
                            change_groups[change_type][:3]
                        )  # 各タイプ最大3件

                for change in important_changes[:6]:  # 最大6件の重要変更を個別表示
                    embeds.append(self.create_embed(change))

            payload = {
                "username": "楽天商品監視Bot",
                "avatar_url": "https://cdn-icons-png.flaticon.com/512/2331/2331970.png",
                "embeds": embeds,
            }

            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code == 204:
                logger.info(
                    f"Discord notification sent successfully: {total_changes} changes ({len(embeds)} embeds)"
                )
                return True
            else:
                logger.error(
                    f"Discord notification failed: {response.status_code} - {response.text}"
                )
                return False

        except requests.RequestException as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in Discord notification: {e}")
            return False

    def test_webhook(self) -> bool:
        """Webhook接続をテスト"""
        if not self.webhook_url:
            logger.error("Discord webhook URL not configured")
            return False

        test_embed = {
            "title": "🧪 楽天商品監視システム テスト",
            "description": "Discord Webhook接続テストが成功しました！",
            "color": 0x00FF00,
            "timestamp": datetime.now().isoformat(),
            "fields": [{"name": "ステータス", "value": "正常動作中", "inline": True}],
        }

        payload = {"username": "楽天商品監視Bot", "embeds": [test_embed]}

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code == 204:
                logger.info("Discord webhook test successful")
                return True
            else:
                logger.error(f"Discord webhook test failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Discord webhook test error: {e}")
            return False

    def notify_error(
        self, title: str, description: str, error_details: Optional[str] = None
    ) -> bool:
        """エラー通知をDiscord #alertsチャンネルに送信"""
        webhook_url = self.alert_webhook_url or self.webhook_url

        if not webhook_url:
            logger.warning(
                "Discord alert webhook URL not configured, skipping error notification"
            )
            return False

        error_embed = {
            "title": f"🚨 {title}",
            "description": description,
            "color": 0xFF0000,  # 赤色
            "timestamp": datetime.now().isoformat(),
            "fields": [
                {"name": "システム", "value": "楽天商品監視システム", "inline": True},
                {
                    "name": "発生時刻",
                    "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "inline": True,
                },
            ],
        }

        # エラー詳細があれば追加
        if error_details:
            error_embed["fields"].append(
                {
                    "name": "エラー詳細",
                    "value": f"```{error_details[:1000]}```",  # 1000文字制限
                    "inline": False,
                }
            )

        payload = {
            "username": "監視システムアラート",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/564/564619.png",
            "embeds": [error_embed],
        }

        try:
            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code == 204:
                logger.info(f"Discord error notification sent: {title}")
                return True
            else:
                logger.error(
                    f"Discord error notification failed: {response.status_code}"
                )
                return False

        except requests.RequestException as e:
            logger.error(f"Failed to send Discord error notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in Discord error notification: {e}")
            return False


def main():
    """テスト実行"""
    notifier = DiscordNotifier()

    # テスト用の変更データ
    test_changes = [
        {
            "type": "NEW",
            "code": "test-001",
            "title": "テスト商品 - 新商品",
            "price": 3980,
            "url": "https://example.com/test-001",
            "in_stock": True,
        }
    ]

    success = notifier.send_notification(test_changes)
    print(f"Notification test: {'Success' if success else 'Failed'}")


if __name__ == "__main__":
    main()
