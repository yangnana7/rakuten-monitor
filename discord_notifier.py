"""Discord Webhook通知機能"""
import requests
import logging
import time
from typing import Dict, Any
from .exceptions import DiscordNotificationError


logger = logging.getLogger(__name__)


class DiscordNotifier:
    """Discord Webhook通知を送信するクラス"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.max_retries = 3
        self.base_delay = 1.0
    
    def send_notification(self, message: str, retry_count: int = 0) -> bool:
        """Discord通知を送信（リトライ機能付き）"""
        try:
            payload = {
                "content": message,
                "username": "楽天商品監視ツール"
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 204:
                logger.info("Discord notification sent successfully")
                return True
            elif response.status_code == 429:
                # Rate limit - リトライ
                retry_after = int(response.headers.get('Retry-After', self.base_delay))
                if retry_count < self.max_retries:
                    logger.warning(f"Rate limited, retrying after {retry_after}s")
                    time.sleep(retry_after)
                    return self.send_notification(message, retry_count + 1)
                else:
                    raise DiscordNotificationError(f"Rate limit exceeded after {self.max_retries} retries")
            else:
                error_msg = f"Discord API error: {response.status_code} {response.text}"
                if retry_count < self.max_retries:
                    delay = self.base_delay * (2 ** retry_count)
                    logger.warning(f"{error_msg}, retrying in {delay}s")
                    time.sleep(delay)
                    return self.send_notification(message, retry_count + 1)
                else:
                    raise DiscordNotificationError(error_msg)
                    
        except requests.exceptions.RequestException as e:
            if retry_count < self.max_retries:
                delay = self.base_delay * (2 ** retry_count)
                logger.warning(f"Network error: {e}, retrying in {delay}s")
                time.sleep(delay)
                return self.send_notification(message, retry_count + 1)
            else:
                raise DiscordNotificationError(f"Network error after {self.max_retries} retries: {e}")
    
    def notify_new_item(self, item_data: Dict[str, Any]) -> bool:
        """新商品通知"""
        message = (
            f"【新商品】{item_data['name']}が入荷しました！ "
            f"{item_data['price']} {item_data['url']}"
        )
        return self.send_notification(message)
    
    def notify_restock(self, item_data: Dict[str, Any]) -> bool:
        """再販通知"""
        message = (
            f"【再販】{item_data['name']}の在庫が復活しました！ "
            f"{item_data['price']} {item_data['url']}"
        )
        return self.send_notification(message)
    
    def notify_error(self, error_type: str, error_message: str) -> bool:
        """エラー通知"""
        if error_type == "layout":
            message = "警告: ページの構造が変更された可能性があります。ツールのメンテナンスが必要です。"
        elif error_type == "db":
            message = "重大なエラー: データベースに接続できません。システムを確認してください。"
        elif error_type == "discord":
            message = f"Discord通知エラー: {error_message}"
        else:
            message = f"監視エラー ({error_type}): {error_message}"
        
        try:
            return self.send_notification(message)
        except DiscordNotificationError:
            # Discord通知自体が失敗した場合はログに記録のみ
            logger.error(f"Failed to send error notification: {message}")
            return False
    
    def test_connection(self) -> bool:
        """Webhook接続テスト"""
        try:
            test_message = "楽天商品監視ツール接続テスト"
            return self.send_notification(test_message)
        except DiscordNotificationError as e:
            logger.error(f"Discord connection test failed: {e}")
            return False