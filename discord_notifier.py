#!/usr/bin/env python3
"""
Discord Webhook 通知機能
"""

import requests
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class DiscordNotifier:
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv('DISCORD_WEBHOOK_URL')
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured")
    
    def create_embed(self, change: Dict[str, Any]) -> Dict[str, Any]:
        """変更情報からDiscord埋め込みを作成"""
        change_type = change['type']
        title = change.get('title', 'Unknown Product')
        url = change.get('url', '')
        price = change.get('price')
        
        # タイプごとのアイコンと色
        type_config = {
            'NEW': {'emoji': '🆕', 'color': 0x00ff00, 'title_prefix': 'NEW'},
            'RESTOCK': {'emoji': '🔄', 'color': 0x0099ff, 'title_prefix': 'RESTOCK'},
            'TITLE_UPDATE': {'emoji': '📝', 'color': 0xffaa00, 'title_prefix': 'TITLE UPDATE'},
            'PRICE_UPDATE': {'emoji': '💰', 'color': 0xff6600, 'title_prefix': 'PRICE UPDATE'},
            'SOLDOUT': {'emoji': '❌', 'color': 0xff0000, 'title_prefix': 'SOLD OUT'}
        }
        
        config = type_config.get(change_type, type_config['NEW'])
        
        embed = {
            'title': f"{config['emoji']} {config['title_prefix']}: {title[:100]}",
            'url': url,
            'color': config['color'],
            'timestamp': datetime.now().isoformat(),
            'fields': []
        }
        
        # 価格情報
        if price:
            embed['fields'].append({
                'name': '価格',
                'value': f'{price:,}円',
                'inline': True
            })
        
        # 在庫状況
        if 'in_stock' in change:
            stock_status = '○' if change['in_stock'] else '×'
            embed['fields'].append({
                'name': '在庫',
                'value': stock_status,
                'inline': True
            })
        
        # タイトル変更の場合は詳細情報
        if change_type == 'TITLE_UPDATE':
            embed['fields'].extend([
                {
                    'name': '旧タイトル',
                    'value': change.get('old_title', 'Unknown')[:1000],
                    'inline': False
                },
                {
                    'name': '新タイトル', 
                    'value': change.get('new_title', 'Unknown')[:1000],
                    'inline': False
                }
            ])
        # 価格変更の場合は詳細情報
        elif change_type == 'PRICE_UPDATE':
            old_price = change.get('old_price')
            new_price = change.get('new_price')
            if old_price is not None and new_price is not None:
                price_diff = new_price - old_price
                diff_text = f"+{price_diff:,}円" if price_diff > 0 else f"{price_diff:,}円"
                embed['fields'].extend([
                    {
                        'name': '旧価格',
                        'value': f'{old_price:,}円',
                        'inline': True
                    },
                    {
                        'name': '新価格',
                        'value': f'{new_price:,}円',
                        'inline': True
                    },
                    {
                        'name': '価格差',
                        'value': diff_text,
                        'inline': True
                    }
                ])
        
        return embed
    
    def send_notification(self, changes: List[Dict[str, Any]]) -> bool:
        """変更通知をDiscordに送信"""
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured, skipping notification")
            return False
        
        if not changes:
            logger.info("No changes to notify")
            return True
        
        try:
            embeds = [self.create_embed(change) for change in changes[:10]]  # 最大10件
            
            payload = {
                'username': '楽天商品監視Bot',
                'avatar_url': 'https://cdn-icons-png.flaticon.com/512/2331/2331970.png',
                'embeds': embeds
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 204:
                logger.info(f"Discord notification sent successfully: {len(changes)} changes")
                return True
            else:
                logger.error(f"Discord notification failed: {response.status_code} - {response.text}")
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
            'title': '🧪 楽天商品監視システム テスト',
            'description': 'Discord Webhook接続テストが成功しました！',
            'color': 0x00ff00,
            'timestamp': datetime.now().isoformat(),
            'fields': [
                {
                    'name': 'ステータス',
                    'value': '正常動作中',
                    'inline': True
                }
            ]
        }
        
        payload = {
            'username': '楽天商品監視Bot',
            'embeds': [test_embed]
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
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

def main():
    """テスト実行"""
    notifier = DiscordNotifier()
    
    # テスト用の変更データ
    test_changes = [
        {
            'type': 'NEW',
            'code': 'test-001',
            'title': 'テスト商品 - 新商品',
            'price': 3980,
            'url': 'https://example.com/test-001',
            'in_stock': True
        }
    ]
    
    success = notifier.send_notification(test_changes)
    print(f"Notification test: {'Success' if success else 'Failed'}")

if __name__ == "__main__":
    main()