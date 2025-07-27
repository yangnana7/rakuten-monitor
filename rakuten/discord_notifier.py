"""Discord Webhook通知モジュール - Phase3."""
import requests
from datetime import datetime, timezone
from typing import Dict


def send_notification(item_dict: Dict[str, str]) -> bool:
    """
    Discord Webhookに商品通知を送信する。
    
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
        required_fields = ['item_code', 'title', 'status']
        for field in required_fields:
            if field not in item_dict:
                return False
        
        status = item_dict['status']
        
        # UNCHANGEDの場合は通知しない（成功として扱う）
        if status == 'UNCHANGED':
            return True
        
        # ステータスに応じたメッセージ設定
        if status == 'NEW':
            title = "🆕 新商品発見"
            color = 0x00ff00  # Green
        elif status == 'RESALE':
            title = "🔄 再販商品発見"
            color = 0xff9900  # Orange
        else:
            # 未知のステータスの場合はデフォルト
            title = "📦 商品更新"
            color = 0x0099ff  # Blue
        
        # Discord Embed作成
        embed = {
            "title": title,
            "description": f"**{item_dict['title']}**\n\n商品コード: `{item_dict['item_code']}`",
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Webhook payload作成
        payload = {
            "embeds": [embed]
        }
        
        # 環境変数からWebhook URLを取得（テスト時はモック化される）
        webhook_url = _get_webhook_url()
        
        # Webhook送信
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10
        )
        
        # Discord Webhookは成功時に204を返す
        return response.status_code == 204
        
    except Exception:
        # 任意の例外で失敗
        return False


def _get_webhook_url() -> str:
    """
    Discord Webhook URLを取得する。
    
    Returns:
        str: Webhook URL
    """
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    return os.getenv('DISCORD_WEBHOOK_URL', 'https://discord.com/api/webhooks/dummy')