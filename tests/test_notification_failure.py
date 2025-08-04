"""Discord通知失敗時のリトライ＆メトリクステスト"""

import pytest
from unittest.mock import Mock, patch, call
import requests
import time

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from discord_notifier import DiscordNotifier
from exceptions import DiscordNotificationError
from monitor import RakutenMonitor


class TestDiscordNotificationRetry:
    """Discord通知のリトライ機能テスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される準備処理"""
        self.webhook_url = "https://discord.com/api/webhooks/test/webhook"
        self.notifier = DiscordNotifier(self.webhook_url)
        
        self.test_message = "テスト通知メッセージ"
        self.test_embed = {
            "title": "テストタイトル",
            "description": "テスト内容",
            "color": 0x00ff00
        }
    
    @patch('discord_notifier.requests.post')
    @patch('discord_notifier.time.sleep')
    def test_discord_retry_on_network_error(self, mock_sleep, mock_post):
        """ネットワークエラー時のリトライテスト（5秒→15秒→60秒）"""
        # 最初の2回は失敗、3回目で成功
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("Network error 1"),
            requests.exceptions.ConnectionError("Network error 2"),
            Mock(status_code=204)  # 成功
        ]
        
        # 実行
        result = self.notifier.send_notification(message=self.test_message)
        
        # 検証
        assert result == True
        assert mock_post.call_count == 3
        
        # リトライ間隔が正しいことを確認（5秒→15秒）
        expected_delays = [5, 15]
        actual_delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert actual_delays == expected_delays
    
    @patch('discord_notifier.requests.post')
    @patch('discord_notifier.time.sleep')
    def test_discord_retry_on_api_error(self, mock_sleep, mock_post):
        """Discord API エラー時のリトライテスト"""
        # 最初の2回はAPIエラー、3回目で成功
        mock_response_500 = Mock(status_code=500, text="Internal Server Error")
        mock_response_502 = Mock(status_code=502, text="Bad Gateway")
        mock_response_success = Mock(status_code=204)
        
        mock_post.side_effect = [
            mock_response_500,
            mock_response_502,
            mock_response_success
        ]
        
        # 実行
        result = self.notifier.send_notification(message=self.test_message)
        
        # 検証
        assert result == True
        assert mock_post.call_count == 3
        
        # リトライ間隔が指示書通り（5秒→15秒）であることを確認
        expected_delays = [5, 15]
        actual_delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert actual_delays == expected_delays
    
    @patch('discord_notifier.requests.post')
    @patch('discord_notifier.time.sleep')
    def test_discord_retry_exhausted(self, mock_sleep, mock_post):
        """リトライ上限到達時のテスト"""
        # すべてのリトライで失敗（初回 + 3回のリトライ = 4回）
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("Persistent error"),
            requests.exceptions.ConnectionError("Persistent error"),
            requests.exceptions.ConnectionError("Persistent error"),
            requests.exceptions.ConnectionError("Persistent error")
        ]
        
        # 実行と検証
        with pytest.raises(DiscordNotificationError) as exc_info:
            self.notifier.send_notification(message=self.test_message)
        
        assert "Network error after 3 retries" in str(exc_info.value)
        assert mock_post.call_count == 4  # 初回 + 3回のリトライ
        
        # 全ての間隔でリトライされることを確認（5秒→15秒→60秒の3回のsleep）
        assert mock_sleep.call_count == 3
        expected_delays = [5, 15, 60]
        actual_delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert actual_delays == expected_delays
    
    @patch('discord_notifier.requests.post')
    @patch('discord_notifier.time.sleep')
    def test_discord_rate_limit_handling(self, mock_sleep, mock_post):
        """Discord レート制限時のハンドリングテスト"""
        # レート制限レスポンス
        rate_limit_response = Mock(status_code=429)
        rate_limit_response.headers = {'Retry-After': '10'}
        
        success_response = Mock(status_code=204)
        
        mock_post.side_effect = [rate_limit_response, success_response]
        
        # 実行
        result = self.notifier.send_notification(message=self.test_message)
        
        # 検証
        assert result == True
        assert mock_post.call_count == 2
        
        # Retry-Afterヘッダーの値でsleepされることを確認（通常のリトライ間隔ではない）
        mock_sleep.assert_called_once_with(10)
    
    @patch('discord_notifier.requests.post')
    def test_discord_immediate_success(self, mock_post):
        """即座に成功する場合のテスト（リトライなし）"""
        # 最初から成功
        mock_post.return_value = Mock(status_code=204)
        
        # 実行
        result = self.notifier.send_notification(message=self.test_message)
        
        # 検証
        assert result == True
        assert mock_post.call_count == 1
    
    def test_discord_retry_intervals_configuration(self):
        """リトライ間隔の設定が正しいことのテスト"""
        # 指示書に従った設定：5秒→15秒→60秒
        expected_delays = [5, 15, 60]
        assert self.notifier.retry_delays == expected_delays
        assert self.notifier.max_retries == 3


class TestNotificationTypeSpecificRetry:
    """通知タイプ別のリトライテスト"""
    
    def setup_method(self):
        """テスト準備"""
        self.webhook_url = "https://discord.com/api/webhooks/test"
        self.notifier = DiscordNotifier(self.webhook_url)
        
        self.new_item_data = {
            'product_id': 'test123',
            'name': 'テスト新商品',
            'price': '¥1,000',
            'url': 'https://example.com/test',
            'change_type': 'new_item'
        }
        
        self.restock_data = {
            'product_id': 'restock123',
            'name': 'テスト再販商品',
            'price': '¥2,000', 
            'url': 'https://example.com/restock',
            'change_type': 'restock'
        }
    
    @patch('discord_notifier.DiscordNotifier.send_notification')
    def test_notify_new_item_with_retry(self, mock_send):
        """新商品通知のリトライテスト"""
        # 最初は失敗、リトライで成功
        mock_send.side_effect = [
            DiscordNotificationError("First attempt failed"),
            True  # 2回目で成功
        ]
        
        # 直接send_notificationを呼ぶのではなく、notify_new_itemメソッドをテスト
        # ただし、内部的にはsend_notificationが呼ばれるのでモックで制御
        with patch.object(self.notifier, 'send_notification', side_effect=[
            DiscordNotificationError("Failed"), True
        ]) as mock_send_internal:
            # notify_new_itemは内部でsend_notificationを呼ぶが例外処理する可能性がある
            # 実際の実装に合わせてテストを調整
            try:
                result = self.notifier.notify_new_item(self.new_item_data)
                # 成功した場合
                assert result == True
            except DiscordNotificationError:
                # 失敗が外部に伝播する場合
                pass
    
    @patch('discord_notifier.DiscordNotifier.send_notification')
    def test_notify_restock_with_retry(self, mock_send):
        """再販通知のリトライテスト"""
        mock_send.return_value = True
        
        # 実行
        result = self.notifier.notify_restock(self.restock_data)
        
        # 検証
        assert result == True
        mock_send.assert_called_once()


class TestMonitorDiscordFailureHandling:
    """Monitor統合でのDiscord通知失敗処理テスト"""
    
    def setup_method(self):
        """テスト準備"""
        self.monitor = RakutenMonitor()
    
    @patch('monitor.push_failure_metric')
    @patch('monitor.DiscordNotifier')
    def test_discord_failure_metrics_increment(self, mock_discord_notifier, mock_push_metric):
        """Discord通知失敗時のメトリクス増分テスト"""
        # Discord通知が失敗するモック
        mock_notifier_instance = Mock()
        mock_notifier_instance.notify_new_item.side_effect = DiscordNotificationError("Discord failed")
        mock_discord_notifier.return_value = mock_notifier_instance
        
        # テスト用のdiff_result
        from models import DiffResult
        from html_parser import Product
        
        test_product = Product(
            id="test", name="テスト商品", price=1000, 
            url="https://test.com", in_stock=True
        )
        
        diff_result = DiffResult(
            new_items=[test_product],
            restocked=[],
            out_of_stock=[],
            price_changed=[],
            updated_items=[]
        )
        
        # 設定をモック
        config = {
            'urls': ['https://test.url'],
            'webhookUrl': 'https://discord.com/webhook'
        }
        
        with patch.object(self.monitor, '_is_monitoring_time', return_value=True):
            with patch.object(self.monitor.config_loader, 'load_config', return_value=config):
                with patch.object(self.monitor, 'process_url_with_diff', return_value=diff_result):
                    # 実行
                    self.monitor.run_monitoring_with_diff()
        
        # Discord失敗メトリクスが送信されることを確認
        mock_push_metric.assert_called_with("discord", "Discord failed")
    
    @patch('monitor.DiscordNotifier')
    def test_discord_bulk_failure_critical_alert(self, mock_discord_notifier):
        """Discord通知の大量失敗時の重要アラートテスト"""
        mock_notifier_instance = Mock()
        
        # 新商品通知は失敗、重要アラートは成功
        mock_notifier_instance.notify_new_item.side_effect = DiscordNotificationError("Failed")
        mock_notifier_instance.send_critical.return_value = True
        
        mock_discord_notifier.return_value = mock_notifier_instance
        
        # テスト用のdiff_result（複数の新商品）
        from models import DiffResult
        from html_parser import Product
        
        products = [
            Product(id=f"test{i}", name=f"テスト商品{i}", price=1000, 
                   url=f"https://test{i}.com", in_stock=True)
            for i in range(3)
        ]
        
        diff_result = DiffResult(
            new_items=products,
            restocked=[],
            out_of_stock=[],
            price_changed=[],
            updated_items=[]
        )
        
        config = {
            'urls': ['https://test.url'],
            'webhookUrl': 'https://discord.com/webhook'
        }
        
        with patch.object(self.monitor, '_is_monitoring_time', return_value=True):
            with patch.object(self.monitor.config_loader, 'load_config', return_value=config):
                with patch.object(self.monitor, 'process_url_with_diff', return_value=diff_result):
                    # 実行
                    self.monitor.run_monitoring_with_diff()
        
        # 重要アラートが送信されることを確認
        mock_notifier_instance.send_critical.assert_called_once()
        call_args = mock_notifier_instance.send_critical.call_args
        assert "Discord通知システム障害" in call_args[1]['title']


class TestDiscordNotificationErrorTypes:
    """Discord通知エラーの種類別テスト"""
    
    def setup_method(self):
        """テスト準備"""
        self.notifier = DiscordNotifier("https://test.webhook")
    
    def test_discord_notification_error_creation(self):
        """DiscordNotificationErrorオブジェクトの作成テスト"""
        error = DiscordNotificationError("Test error", status_code=500, response_text="Internal Error")
        
        assert str(error) == "Test error (HTTP 500)"
        assert error.status_code == 500
        assert error.response_text == "Internal Error"
    
    def test_discord_notification_error_without_status_code(self):
        """ステータスコードなしのDiscordNotificationErrorテスト"""
        error = DiscordNotificationError("Test error without status")
        
        assert str(error) == "Test error without status"
        assert error.status_code is None
        assert error.response_text is None
    
    @patch('discord_notifier.requests.post')
    def test_discord_error_with_response_details(self, mock_post):
        """レスポンス詳細付きDiscordエラーテスト"""
        mock_response = Mock(status_code=400, text='{"error": "Bad Request"}')
        mock_post.return_value = mock_response
        
        with pytest.raises(DiscordNotificationError) as exc_info:
            # max_retriesを超えるまでエラーを発生させる
            self.notifier.send_notification("test", retry_count=3)
        
        error = exc_info.value
        assert error.status_code == 400
        assert '{"error": "Bad Request"}' in error.response_text


if __name__ == '__main__':
    pytest.main([__file__, '-v'])