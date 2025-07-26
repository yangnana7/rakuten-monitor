#!/usr/bin/env python3
"""
discord_notifier.py のテスト
"""

import pytest
import requests_mock
from unittest.mock import patch
from discord_notifier import DiscordNotifier

class TestDiscordNotifier:
    def setup_method(self):
        """テストセットアップ"""
        self.webhook_url = "https://discord.com/api/webhooks/test"
        self.alert_webhook_url = "https://discord.com/api/webhooks/alert"
        self.notifier = DiscordNotifier(
            webhook_url=self.webhook_url, 
            alert_webhook_url=self.alert_webhook_url
        )

    def test_init_with_urls(self):
        """初期化テスト（URL指定）"""
        notifier = DiscordNotifier(
            webhook_url=self.webhook_url,
            alert_webhook_url=self.alert_webhook_url
        )
        assert notifier.webhook_url == self.webhook_url
        assert notifier.alert_webhook_url == self.alert_webhook_url

    @patch.dict('os.environ', {
        'DISCORD_WEBHOOK_URL': 'https://env.webhook.url',
        'DISCORD_ALERT_WEBHOOK_URL': 'https://env.alert.url'
    })
    def test_init_from_env(self):
        """初期化テスト（環境変数）"""
        notifier = DiscordNotifier()
        assert notifier.webhook_url == 'https://env.webhook.url'
        assert notifier.alert_webhook_url == 'https://env.alert.url'

    def test_create_embed_new_item(self):
        """NEW商品のEmbed作成テスト"""
        change = {
            'type': 'NEW',
            'code': 'item1',
            'title': 'テスト商品',
            'price': 3980,
            'url': 'https://example.com/item1',
            'in_stock': True
        }
        
        embed = self.notifier.create_embed(change)
        
        assert '🆕 NEW' in embed['title']
        assert 'テスト商品' in embed['title']
        assert embed['color'] == 0x00ff00
        assert embed['url'] == 'https://example.com/item1'
        assert any(field['name'] == '価格' and '3,980円' in field['value'] for field in embed['fields'])

    def test_create_embed_price_update(self):
        """価格変更のEmbed作成テスト"""
        change = {
            'type': 'PRICE_UPDATE',
            'code': 'item1',
            'title': 'テスト商品',
            'old_price': 3980,
            'new_price': 4500,
            'url': 'https://example.com/item1'
        }
        
        embed = self.notifier.create_embed(change)
        
        assert '💰 PRICE UPDATE' in embed['title']
        assert embed['color'] == 0xff6600
        
        # 価格変更の詳細フィールドをチェック
        field_names = [field['name'] for field in embed['fields']]
        assert '旧価格' in field_names
        assert '新価格' in field_names
        assert '価格差' in field_names

    def test_create_embed_title_update(self):
        """タイトル変更のEmbed作成テスト"""
        change = {
            'type': 'TITLE_UPDATE',
            'code': 'item1',
            'title': '新タイトル',
            'old_title': '旧タイトル',
            'new_title': '新タイトル'
        }
        
        embed = self.notifier.create_embed(change)
        
        assert '📝 TITLE UPDATE' in embed['title']
        assert embed['color'] == 0xffaa00
        
        # タイトル変更の詳細フィールドをチェック
        field_names = [field['name'] for field in embed['fields']]
        assert '旧タイトル' in field_names
        assert '新タイトル' in field_names

    @requests_mock.Mocker()
    def test_send_notification_success(self, m):
        """通知送信成功テスト"""
        m.post(self.webhook_url, status_code=204)
        
        changes = [{
            'type': 'NEW',
            'code': 'item1',
            'title': 'テスト商品',
            'price': 3980
        }]
        
        result = self.notifier.send_notification(changes)
        
        assert result is True
        assert m.called
        assert m.call_count == 1

    @requests_mock.Mocker()
    def test_send_notification_failure(self, m):
        """通知送信失敗テスト"""
        m.post(self.webhook_url, status_code=400, text="Bad Request")
        
        changes = [{
            'type': 'NEW',
            'code': 'item1',
            'title': 'テスト商品'
        }]
        
        result = self.notifier.send_notification(changes)
        
        assert result is False

    def test_send_notification_no_webhook_url(self):
        """Webhook URL未設定時のテスト"""
        notifier = DiscordNotifier(webhook_url=None)
        
        changes = [{'type': 'NEW', 'code': 'item1'}]
        result = notifier.send_notification(changes)
        
        assert result is False

    def test_send_notification_empty_changes(self):
        """空の変更リストのテスト"""
        result = self.notifier.send_notification([])
        assert result is True

    @requests_mock.Mocker()
    def test_send_notification_max_embeds(self, m):
        """最大Embed数制限のテスト"""
        m.post(self.webhook_url, status_code=204)
        
        # 15個の変更を作成（制限は10個）
        changes = [{'type': 'NEW', 'code': f'item{i}', 'title': f'商品{i}'} for i in range(15)]
        
        result = self.notifier.send_notification(changes)
        
        assert result is True
        
        # リクエストボディを確認（最大10個のembedが送信される）
        request_body = m.request_history[0].json()
        assert len(request_body['embeds']) == 10

    @requests_mock.Mocker()
    def test_test_webhook_success(self, m):
        """Webhookテスト成功"""
        m.post(self.webhook_url, status_code=204)
        
        result = self.notifier.test_webhook()
        
        assert result is True
        assert m.called

    @requests_mock.Mocker()
    def test_test_webhook_failure(self, m):
        """Webhookテスト失敗"""
        m.post(self.webhook_url, status_code=400)
        
        result = self.notifier.test_webhook()
        
        assert result is False

    def test_test_webhook_no_url(self):
        """Webhook URL未設定時のテスト"""
        notifier = DiscordNotifier(webhook_url=None)
        
        result = notifier.test_webhook()
        
        assert result is False

    @requests_mock.Mocker()
    def test_notify_error_success(self, m):
        """エラー通知成功テスト"""
        m.post(self.alert_webhook_url, status_code=204)
        
        result = self.notifier.notify_error(
            title="テストエラー",
            description="テストエラーの説明",
            error_details="詳細なエラー情報"
        )
        
        assert result is True
        assert m.called
        
        # リクエストボディの確認
        request_body = m.request_history[0].json()
        assert '🚨 テストエラー' in request_body['embeds'][0]['title']
        assert request_body['embeds'][0]['color'] == 0xff0000

    @requests_mock.Mocker()
    def test_notify_error_fallback_to_main_webhook(self, m):
        """アラートWebhook未設定時のメインWebhookフォールバック"""
        notifier = DiscordNotifier(webhook_url=self.webhook_url, alert_webhook_url=None)
        m.post(self.webhook_url, status_code=204)
        
        result = notifier.notify_error("テストエラー", "説明")
        
        assert result is True
        assert m.called

    def test_notify_error_no_webhook(self):
        """Webhook URL未設定時のエラー通知テスト"""
        notifier = DiscordNotifier(webhook_url=None, alert_webhook_url=None)
        
        result = notifier.notify_error("テストエラー", "説明")
        
        assert result is False

    @requests_mock.Mocker()
    def test_notify_error_with_long_details(self, m):
        """長いエラー詳細の切り捨てテスト"""
        m.post(self.alert_webhook_url, status_code=204)
        
        long_error_details = "エラー詳細" * 200  # 1000文字を超える文字列
        
        result = self.notifier.notify_error(
            title="テストエラー",
            description="説明",
            error_details=long_error_details
        )
        
        assert result is True
        
        # エラー詳細が1000文字に切り捨てられることを確認
        request_body = m.request_history[0].json()
        error_field = next(
            field for field in request_body['embeds'][0]['fields'] 
            if field['name'] == 'エラー詳細'
        )
        assert len(error_field['value']) <= 1003  # ```で囲まれるので+3

if __name__ == "__main__":
    pytest.main([__file__, "-v"])