"""Discord Webhook通知機能"""
import requests
import logging
import time
from typing import Dict, Any, Optional
try:
    from .exceptions import DiscordNotificationError
except ImportError:
    from exceptions import DiscordNotificationError


logger = logging.getLogger(__name__)


class DiscordNotifier:
    """Discord Webhook通知を送信するクラス"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.max_retries = 3
        self.base_delay = 1.0
    
    def send_notification(self, message: str = None, embed: Dict[str, Any] = None, retry_count: int = 0) -> bool:
        """Discord通知を送信（リトライ機能付き）"""
        try:
            payload = {
                "username": "楽天商品監視ツール"
            }
            
            if message:
                payload["content"] = message
            
            if embed:
                payload["embeds"] = [embed]
            
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
                    return self.send_notification(message, embed, retry_count + 1)
                else:
                    raise DiscordNotificationError(f"Rate limit exceeded after {self.max_retries} retries")
            else:
                error_msg = f"Discord API error: {response.status_code} {response.text}"
                if retry_count < self.max_retries:
                    delay = self.base_delay * (2 ** retry_count)
                    logger.warning(f"{error_msg}, retrying in {delay}s")
                    time.sleep(delay)
                    return self.send_notification(message, embed, retry_count + 1)
                else:
                    raise DiscordNotificationError(error_msg, response.status_code, response.text)
                    
        except requests.exceptions.RequestException as e:
            if retry_count < self.max_retries:
                delay = self.base_delay * (2 ** retry_count)
                logger.warning(f"Network error: {e}, retrying in {delay}s")
                time.sleep(delay)
                return self.send_notification(message, embed, retry_count + 1)
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
    
    def send_warning(self, title: str, message: str, details: str = None) -> bool:
        """警告レベルの通知を送信（黄色のEmbed）"""
        embed = {
            "title": f"⚠️ 警告: {title}",
            "description": message,
            "color": 0xFFFF00,  # 黄色
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "footer": {
                "text": "楽天商品監視ツール"
            }
        }
        
        if details:
            embed["fields"] = [{
                "name": "詳細",
                "value": details[:1024],  # Discord の制限
                "inline": False
            }]
        
        try:
            return self.send_notification(embed=embed)
        except DiscordNotificationError as e:
            logger.error(f"Failed to send warning notification: {e}")
            return False
    
    def send_critical(self, title: str, message: str, details: str = None) -> bool:
        """重大エラーレベルの通知を送信（赤色のEmbed）"""
        embed = {
            "title": f"🚨 重大エラー: {title}",
            "description": message,
            "color": 0xFF0000,  # 赤色
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "footer": {
                "text": "楽天商品監視ツール"
            }
        }
        
        if details:
            embed["fields"] = [{
                "name": "エラー詳細",
                "value": details[:1024],  # Discord の制限
                "inline": False
            }]
        
        try:
            return self.send_notification(embed=embed)
        except DiscordNotificationError as e:
            logger.error(f"Failed to send critical notification: {e}")
            return False
    
    def send_info(self, title: str, message: str, details: str = None) -> bool:
        """情報レベルの通知を送信（青色のEmbed）"""
        embed = {
            "title": f"ℹ️ 情報: {title}",
            "description": message,
            "color": 0x0099FF,  # 青色
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "footer": {
                "text": "楽天商品監視ツール"
            }
        }
        
        if details:
            embed["fields"] = [{
                "name": "詳細情報",
                "value": details[:1024],  # Discord の制限
                "inline": False
            }]
        
        try:
            return self.send_notification(embed=embed)
        except DiscordNotificationError as e:
            logger.error(f"Failed to send info notification: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Webhook接続テスト"""
        try:
            return self.send_info(
                title="接続テスト",
                message="Discord Webhook 接続テストが正常に完了しました。",
                details="この通知が表示されれば、監視ツールからの通知が正常に機能しています。"
            )
        except DiscordNotificationError as e:
            logger.error(f"Discord connection test failed: {e}")
            return False