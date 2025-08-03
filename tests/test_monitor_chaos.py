"""Chaos テスト - 例外処理とエラー通知の堅牢性テスト"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import requests

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitor import RakutenMonitor
from exceptions import (
    LayoutChangeError, 
    DatabaseConnectionError, 
    DiscordNotificationError,
    NetworkError,
    PrometheusError
)
from discord_notifier import DiscordNotifier
from prometheus_client import PrometheusClient


class TestLayoutChangeDetection:
    """BDD シナリオ6: レイアウト変更検出テスト"""
    
    @pytest.fixture
    def monitor(self):
        """テスト用のモニターインスタンス"""
        with patch('monitor.ConfigLoader') as mock_config:
            mock_config.return_value.load_config.return_value = {
                'urls': ['https://test.rakuten.co.jp/test-item/'],
                'webhookUrl': 'https://discord.com/api/webhooks/test'
            }
            monitor = RakutenMonitor()
            monitor.notifier = Mock(spec=DiscordNotifier)
            return monitor
    
    def test_layout_change_triggers_warning_notification(self, monitor):
        """レイアウト変更時に警告通知が送信されるテスト"""
        test_url = "https://test.rakuten.co.jp/test-item/"
        
        # HTML取得は成功するが、商品情報抽出で失敗するパターン
        mock_html = "<html><body>商品が見つかりません</body></html>"
        
        with patch.object(monitor, '_fetch_page', return_value=mock_html), \
             patch.object(monitor, '_extract_product_info', side_effect=LayoutChangeError("商品セレクタが見つかりません")), \
             patch('monitor.push_failure_metric') as mock_prometheus:
            
            # LayoutChangeErrorが発生することを確認
            with pytest.raises(LayoutChangeError):
                monitor._process_url(test_url)
            
            # Discord警告通知が呼ばれたことを確認
            monitor.notifier.send_warning.assert_called_once()
            call_args = monitor.notifier.send_warning.call_args[1]
            assert call_args['title'] == "ページ構造変更"
            assert "楽天市場のページ構造が変更された" in call_args['message']
            assert test_url in call_args['details']
            
            # Prometheusメトリクスが送信されたことを確認
            mock_prometheus.assert_called_once_with("layout", "商品セレクタが見つかりません")
    
    def test_404_error_triggers_layout_change_error(self, monitor):
        """404エラーがLayoutChangeErrorを引き起こすテスト"""
        test_url = "https://test.rakuten.co.jp/non-existent-item/"
        
        # 404 HTTPErrorをシミュレート
        mock_response = Mock()
        mock_response.status_code = 404
        http_error = requests.exceptions.HTTPError(response=mock_response)
        
        with patch.object(monitor, '_fetch_page', side_effect=LayoutChangeError("ページが見つかりません (404)")):
            with pytest.raises(LayoutChangeError) as exc_info:
                monitor._process_url(test_url)
            
            assert "404" in str(exc_info.value)
    
    def test_discord_notification_failure_during_layout_error(self, monitor):
        """レイアウトエラー時にDiscord通知が失敗した場合のハンドリング"""
        test_url = "https://test.rakuten.co.jp/test-item/"
        
        # Discord通知が失敗するように設定
        monitor.notifier.send_warning.side_effect = DiscordNotificationError("Webhook URL invalid")
        
        with patch.object(monitor, '_fetch_page', return_value="<html></html>"), \
             patch.object(monitor, '_extract_product_info', side_effect=LayoutChangeError("レイアウト変更")), \
             patch('monitor.push_failure_metric') as mock_prometheus:
            
            # LayoutChangeErrorは正常に発生するが、Discord通知エラーは抑制される
            with pytest.raises(LayoutChangeError):
                monitor._process_url(test_url)
            
            # Prometheusメトリクスは正常に送信される
            mock_prometheus.assert_called_once_with("layout", "レイアウト変更")


class TestDatabaseConnectionError:
    """BDD シナリオ7: データベース接続エラーテスト"""
    
    @pytest.fixture
    def monitor(self):
        """テスト用のモニターインスタンス"""
        with patch('monitor.ConfigLoader') as mock_config:
            mock_config.return_value.load_config.return_value = {
                'urls': ['https://test.rakuten.co.jp/test-item/'],
                'webhookUrl': 'https://discord.com/api/webhooks/test'
            }
            monitor = RakutenMonitor()
            monitor.notifier = Mock(spec=DiscordNotifier)
            return monitor
    
    def test_database_error_triggers_critical_notification(self, monitor):
        """データベース接続エラー時に重大エラー通知が送信されるテスト"""
        test_url = "https://test.rakuten.co.jp/test-item/"
        
        # 正常なHTML取得と商品抽出をモック
        mock_html = "<html><body><h1>テスト商品</h1><span class='price'>1000円</span></body></html>"
        mock_product = {
            'product_id': 'test123',
            'name': 'テスト商品',
            'price': '1000円',
            'status': '在庫あり',
            'url': test_url
        }
        
        # データベース接続エラーをシミュレート
        with patch.object(monitor, '_fetch_page', return_value=mock_html), \
             patch.object(monitor, '_extract_product_info', return_value=[mock_product]), \
             patch('monitor.ItemDB') as mock_itemdb, \
             patch('monitor.push_failure_metric') as mock_prometheus:
            
            # ItemDBのコンテキストマネージャでエラーを発生
            mock_itemdb.return_value.__enter__.side_effect = DatabaseConnectionError("PostgreSQL connection failed")
            
            # DatabaseConnectionErrorが発生することを確認
            with pytest.raises(DatabaseConnectionError):
                monitor._process_url(test_url)
            
            # Discord重大エラー通知が呼ばれたことを確認
            monitor.notifier.send_critical.assert_called_once()
            call_args = monitor.notifier.send_critical.call_args[1]
            assert call_args['title'] == "データベース接続エラー"
            assert "PostgreSQLデータベースに接続できません" in call_args['message']
            
            # Prometheusメトリクスが送信されたことを確認
            mock_prometheus.assert_called_once_with("db", "PostgreSQL connection failed")
    
    def test_prometheus_failure_during_db_error(self, monitor):
        """DB接続エラー時にPrometheus送信も失敗した場合のハンドリング"""
        test_url = "https://test.rakuten.co.jp/test-item/"
        
        with patch.object(monitor, '_fetch_page', return_value="<html></html>"), \
             patch.object(monitor, '_extract_product_info', return_value=[]), \
             patch('monitor.ItemDB') as mock_itemdb, \
             patch('monitor.push_failure_metric', side_effect=PrometheusError("Pushgateway unreachable")):
            
            mock_itemdb.return_value.__enter__.side_effect = DatabaseConnectionError("DB down")
            
            # DatabaseConnectionErrorは正常に発生
            with pytest.raises(DatabaseConnectionError):
                monitor._process_url(test_url)
            
            # Discord通知は正常に実行される（Prometheusエラーに影響されない）
            monitor.notifier.send_critical.assert_called_once()


class TestDiscordNotificationError:
    """BDD シナリオ8: Discord通知システム障害テスト"""
    
    @pytest.fixture
    def monitor(self):
        """テスト用のモニターインスタンス"""
        with patch('monitor.ConfigLoader') as mock_config:
            mock_config.return_value.load_config.return_value = {
                'urls': ['https://test.rakuten.co.jp/item1/', 'https://test.rakuten.co.jp/item2/'],
                'webhookUrl': 'https://discord.com/api/webhooks/test'
            }
            monitor = RakutenMonitor()
            return monitor
    
    def test_discord_webhook_failure_metrics(self, monitor):
        """Discord Webhook障害時のメトリクス記録テスト"""
        # 商品変更を検出するが、Discord通知が全て失敗するシナリオ
        mock_changes = [
            {
                'change_type': 'new_item',
                'name': 'テスト商品1',
                'price': '1000円',
                'status': '在庫あり',
                'url': 'https://test.rakuten.co.jp/item1/'
            },
            {
                'change_type': 'restock',
                'name': 'テスト商品2',
                'price': '2000円',
                'status': '在庫あり',
                'url': 'https://test.rakuten.co.jp/item2/'
            }
        ]
        
        with patch.object(monitor, '_is_monitoring_time', return_value=True), \
             patch.object(monitor, '_process_url') as mock_process, \
             patch('monitor.DiscordNotifier') as mock_discord_class, \
             patch('monitor.push_failure_metric') as mock_prometheus_failure, \
             patch('monitor.push_monitoring_metric') as mock_prometheus_monitoring:
            
            # _process_urlは変更を返す
            mock_process.side_effect = [mock_changes[:1], mock_changes[1:]]
            
            # Discord通知は全て失敗
            mock_notifier = Mock()
            mock_notifier.notify_new_item.side_effect = DiscordNotificationError("Rate limit exceeded")
            mock_notifier.notify_restock.side_effect = DiscordNotificationError("Webhook invalid")
            mock_notifier.send_critical.side_effect = DiscordNotificationError("Discord API down")
            mock_discord_class.return_value = mock_notifier
            
            # 監視実行
            monitor.run_monitoring()
            
            # Discord障害メトリクスが記録されることを確認
            assert mock_prometheus_failure.call_count == 2  # 2つの通知失敗
            failure_calls = mock_prometheus_failure.call_args_list
            assert all(call[0][0] == "discord" for call in failure_calls)
            
            # 監視完了メトリクスも記録される
            mock_prometheus_monitoring.assert_called_once()
    
    def test_mass_discord_failure_triggers_critical_alert(self, monitor):
        """大量のDiscord通知失敗時に重大エラー通知がトリガーされるテスト"""
        # 4個の変更があり、3個以上失敗する場合のテスト
        mock_changes = [
            {'change_type': 'new_item', 'name': f'商品{i}', 'price': f'{i*1000}円', 'status': '在庫あり', 'url': f'https://test.rakuten.co.jp/item{i}/'}
            for i in range(1, 5)
        ]
        
        with patch.object(monitor, '_is_monitoring_time', return_value=True), \
             patch.object(monitor, '_process_url', return_value=mock_changes), \
             patch('monitor.DiscordNotifier') as mock_discord_class, \
             patch('monitor.push_failure_metric') as mock_prometheus_failure:
            
            mock_notifier = Mock()
            # 4回中3回失敗（半数以上失敗）
            mock_notifier.notify_new_item.side_effect = [
                DiscordNotificationError("Failed 1"),
                True,  # 成功
                DiscordNotificationError("Failed 2"),
                DiscordNotificationError("Failed 3")
            ]
            # 重大エラー通知も失敗（Discord完全ダウン）
            mock_notifier.send_critical.side_effect = DiscordNotificationError("Complete failure")
            mock_discord_class.return_value = mock_notifier
            
            # 監視実行
            monitor.run_monitoring()
            
            # 個別通知失敗のメトリクス（3回）
            assert mock_prometheus_failure.call_count == 3
            
            # 重大エラー通知が試行されたことを確認
            mock_notifier.send_critical.assert_called_once()
            call_args = mock_notifier.send_critical.call_args[1]
            assert "Discord通知システム障害" in call_args['title']
            assert "3/4" in call_args['message']


class TestPrometheusIntegration:
    """Prometheus メトリクス統合テスト"""
    
    def test_prometheus_client_push_metric(self):
        """PrometheusClient のメトリクス送信テスト"""
        pushgateway_url = "http://localhost:9091"
        client = PrometheusClient(pushgateway_url=pushgateway_url)
        
        with patch('prometheus_client.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            # カウンターメトリクス送信
            result = client.increment_counter(
                name="test_failures_total",
                labels={"type": "layout", "instance": "test"},
                help_text="Test failure counter"
            )
            
            assert result is True
            mock_post.assert_called_once()
            
            # リクエスト内容の確認
            call_args = mock_post.call_args
            assert call_args[0][0] == f"{pushgateway_url}/metrics/job/rakuten_monitor"
            assert 'test_failures_total{type="layout",instance="test"} 1' in call_args[1]['data']
    
    def test_prometheus_disabled_when_no_url(self):
        """Pushgateway URL未設定時はメトリクス送信が無効になるテスト"""
        client = PrometheusClient(pushgateway_url=None)
        
        # メトリクス送信は成功を返すが、実際には何もしない
        result = client.increment_counter("test_metric", {"type": "test"})
        assert result is True
        assert not client.enabled
    
    def test_prometheus_connection_error_handling(self):
        """Prometheus接続エラー時の例外ハンドリングテスト"""
        client = PrometheusClient(pushgateway_url="http://unreachable:9091")
        
        with patch('prometheus_client.requests.post', side_effect=requests.exceptions.ConnectionError("Connection refused")):
            with pytest.raises(PrometheusError) as exc_info:
                client.increment_counter("test_metric", {"type": "test"})
            
            assert "Connection refused" in str(exc_info.value)
            assert exc_info.value.metric_name == "test_metric"


class TestChaosScenarios:
    """統合Chaosテスト - 複数障害の同時発生"""
    
    @pytest.fixture
    def monitor(self):
        """テスト用のモニターインスタンス"""
        with patch('monitor.ConfigLoader') as mock_config:
            mock_config.return_value.load_config.return_value = {
                'urls': ['https://chaos.rakuten.co.jp/unstable-item/'],
                'webhookUrl': 'https://discord.com/api/webhooks/test'
            }
            monitor = RakutenMonitor()
            return monitor
    
    def test_cascade_failure_scenario(self, monitor):
        """カスケード障害シナリオ: レイアウト変更 → Discord障害 → Prometheus障害"""
        test_url = "https://chaos.rakuten.co.jp/unstable-item/"
        
        with patch.object(monitor, '_fetch_page', return_value="<html></html>"), \
             patch.object(monitor, '_extract_product_info', side_effect=LayoutChangeError("完全にレイアウトが変更された")), \
             patch('monitor.DiscordNotifier') as mock_discord_class, \
             patch('monitor.push_failure_metric', side_effect=PrometheusError("All monitoring systems down")):
            
            # Discord通知も失敗
            mock_notifier = Mock()
            mock_notifier.send_warning.side_effect = DiscordNotificationError("Discord system failure")
            mock_discord_class.return_value = mock_notifier
            monitor.notifier = mock_notifier
            
            # 複数システム障害でもLayoutChangeErrorは正常に発生
            with pytest.raises(LayoutChangeError):
                monitor._process_url(test_url)
            
            # 各システムが試行されたことを確認
            mock_notifier.send_warning.assert_called_once()
    
    def test_partial_recovery_scenario(self, monitor):
        """部分復旧シナリオ: 一部の通知システムは復旧"""
        mock_changes = [
            {'change_type': 'new_item', 'name': '復旧テスト商品', 'price': '500円', 'status': '在庫あり', 'url': 'https://test.rakuten.co.jp/recovery/'}
        ]
        
        with patch.object(monitor, '_is_monitoring_time', return_value=True), \
             patch.object(monitor, '_process_url', return_value=mock_changes), \
             patch('monitor.DiscordNotifier') as mock_discord_class, \
             patch('monitor.push_failure_metric') as mock_prometheus_failure, \
             patch('monitor.push_monitoring_metric') as mock_prometheus_monitoring:
            
            mock_notifier = Mock()
            # Discord通知は成功
            mock_notifier.notify_new_item.return_value = True
            mock_discord_class.return_value = mock_notifier
            
            # Prometheus個別エラーメトリクスは失敗するが、監視メトリクスは成功
            mock_prometheus_failure.side_effect = PrometheusError("Partial failure")
            mock_prometheus_monitoring.return_value = True
            
            # 監視実行（例外は発生しない）
            monitor.run_monitoring()
            
            # Discord通知は成功
            mock_notifier.notify_new_item.assert_called_once()
            
            # 監視完了メトリクスは送信される
            mock_prometheus_monitoring.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])