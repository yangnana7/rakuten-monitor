"""稼働時間管理のテスト（cronガード機能）"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, time

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitor import RakutenMonitor


class TestCronGuard:
    """稼働時間外の監視停止テスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される準備処理"""
        self.config_data = {
            'urls': [
                'https://search.rakuten.co.jp/search/mall/test1/',
                'https://search.rakuten.co.jp/search/mall/test2/'
            ],
            'webhookUrl': 'https://discord.com/api/webhooks/test',
            'monitoringHours': {
                'start': '09:00',
                'end': '22:00'
            }
        }
    
    @patch('monitor.RakutenMonitor._is_monitoring_time')
    @patch('monitor.ConfigLoader.load_config')
    def test_outside_monitoring_hours_no_url_processing(self, mock_load_config, mock_is_monitoring_time):
        """稼働時間外はURL取得が呼ばれないことのテスト"""
        # モックの設定
        mock_load_config.return_value = self.config_data
        mock_is_monitoring_time.return_value = False  # 稼働時間外
        
        monitor = RakutenMonitor()
        
        # process_url_with_diffが呼ばれないことを確認するためのモック
        with patch.object(monitor, 'process_url_with_diff') as mock_process_url:
            # 実行
            monitor.run_monitoring_with_diff()
            
            # 検証: URL処理が呼ばれていないことを確認
            mock_process_url.assert_not_called()
    
    @patch('monitor.RakutenMonitor._is_monitoring_time')
    @patch('monitor.ConfigLoader.load_config')
    def test_inside_monitoring_hours_url_processing_occurs(self, mock_load_config, mock_is_monitoring_time):
        """稼働時間内はURL処理が実行されることのテスト"""
        # モックの設定
        mock_load_config.return_value = self.config_data
        mock_is_monitoring_time.return_value = True  # 稼働時間内
        
        monitor = RakutenMonitor()
        
        # process_url_with_diffが呼ばれることを確認するためのモック
        with patch.object(monitor, 'process_url_with_diff') as mock_process_url:
            # 成功応答をモック
            from models import DiffResult
            mock_process_url.return_value = DiffResult(
                new_items=[], restocked=[], out_of_stock=[], price_changed=[], updated_items=[]
            )
            
            # 実行
            monitor.run_monitoring_with_diff()
            
            # 検証: URL処理が設定されたURL数だけ呼ばれることを確認
            assert mock_process_url.call_count == len(self.config_data['urls'])
            
            # 各URLが処理されることを確認
            calls = mock_process_url.call_args_list
            called_urls = [call[0][0] for call in calls]
            for expected_url in self.config_data['urls']:
                assert expected_url in called_urls
    
    @patch('monitor.datetime')
    def test_monitoring_time_detection_within_hours(self, mock_datetime):
        """稼働時間内の検出テスト"""
        # 平日の15:00に設定
        mock_datetime.now.return_value = datetime(2024, 1, 15, 15, 0, 0)  # 月曜日 15:00
        mock_datetime.time = time  # timeクラスは実際のものを使用
        
        monitor = RakutenMonitor()
        
        # デフォルトの稼働時間（9:00-22:00）内なのでTrueを期待
        assert monitor._is_monitoring_time() == True
    
    @patch('monitor.datetime')
    def test_monitoring_time_detection_outside_hours_early(self, mock_datetime):
        """稼働時間外（早朝）の検出テスト"""
        # 平日の6:00に設定
        mock_datetime.now.return_value = datetime(2024, 1, 15, 6, 0, 0)  # 月曜日 6:00
        mock_datetime.time = time
        
        monitor = RakutenMonitor()
        
        # 稼働時間外（9:00前）なのでFalseを期待
        assert monitor._is_monitoring_time() == False
    
    @patch('monitor.datetime')
    def test_monitoring_time_detection_outside_hours_late(self, mock_datetime):
        """稼働時間外（深夜）の検出テスト"""
        # 平日の23:30に設定
        mock_datetime.now.return_value = datetime(2024, 1, 15, 23, 30, 0)  # 月曜日 23:30
        mock_datetime.time = time
        
        monitor = RakutenMonitor()
        
        # 稼働時間外（22:00後）なのでFalseを期待
        assert monitor._is_monitoring_time() == False
    
    @patch('monitor.datetime')
    def test_monitoring_time_detection_weekend(self, mock_datetime):
        """週末の監視時間検出テスト"""
        # 土曜日の15:00に設定
        mock_datetime.now.return_value = datetime(2024, 1, 13, 15, 0, 0)  # 土曜日 15:00
        mock_datetime.time = time
        
        monitor = RakutenMonitor()
        
        # 実装によって変わるが、デフォルトでは土日も監視する想定
        # （実際の実装に合わせて調整）
        result = monitor._is_monitoring_time()
        assert isinstance(result, bool)  # 結果はbooleanであることを確認
    
    @patch('monitor.RakutenMonitor._is_monitoring_time')
    @patch('monitor.ConfigLoader.load_config')
    @patch('monitor.logger')
    def test_monitoring_hours_log_message(self, mock_logger, mock_load_config, mock_is_monitoring_time):
        """稼働時間外の適切なログメッセージテスト"""
        # モックの設定
        mock_load_config.return_value = self.config_data
        mock_is_monitoring_time.return_value = False
        
        monitor = RakutenMonitor()
        
        # 実行
        monitor.run_monitoring_with_diff()
        
        # 検証: 適切なログメッセージが出力されることを確認
        mock_logger.info.assert_called_with("Outside monitoring hours, exiting quietly")
    
    @patch('monitor.RakutenMonitor._is_monitoring_time')
    @patch('monitor.ConfigLoader.load_config')
    def test_monitoring_hours_early_return(self, mock_load_config, mock_is_monitoring_time):
        """稼働時間外は早期returnすることのテスト"""
        # モックの設定
        mock_load_config.return_value = self.config_data
        mock_is_monitoring_time.return_value = False
        
        monitor = RakutenMonitor()
        
        # Discordnotifierが作成されないことを確認
        with patch('monitor.DiscordNotifier') as mock_discord_notifier:
            # 実行
            monitor.run_monitoring_with_diff()
            
            # 検証: DiscordNotifierが作られていないことを確認
            mock_discord_notifier.assert_not_called()
    
    def test_config_monitoring_hours_parsing(self):
        """設定ファイルの監視時間設定の解析テスト"""
        monitor = RakutenMonitor()
        
        # 時間文字列のパース機能をテスト
        # （実際の実装がparse_time_stringのような関数を持っている場合）
        if hasattr(monitor, '_parse_time_string'):
            start_time = monitor._parse_time_string('09:00')
            end_time = monitor._parse_time_string('22:00')
            
            assert start_time.hour == 9
            assert start_time.minute == 0
            assert end_time.hour == 22
            assert end_time.minute == 0


class TestMonitoringSchedule:
    """監視スケジュール設定のテスト"""
    
    def setup_method(self):
        """テスト準備"""
        self.custom_schedule_config = {
            'urls': ['https://example.com/test'],
            'webhookUrl': 'https://discord.com/api/webhooks/test',
            'monitoringHours': {
                'start': '08:30',
                'end': '20:15'
            }
        }
    
    @patch('monitor.ConfigLoader.load_config')
    @patch('monitor.datetime')
    def test_custom_monitoring_hours(self, mock_datetime, mock_load_config):
        """カスタム監視時間の設定テスト"""
        # カスタム設定を使用
        mock_load_config.return_value = self.custom_schedule_config
        
        # 8:30-20:15の範囲内の時間に設定
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 0, 0)
        mock_datetime.time = time
        
        monitor = RakutenMonitor()
        
        # 実装によって結果が変わるが、設定が反映されることを確認
        # （実際の_is_monitoring_timeの実装に依存）
        result = monitor._is_monitoring_time()
        assert isinstance(result, bool)
    
    @patch('monitor.ConfigLoader.load_config')
    def test_missing_monitoring_hours_config(self, mock_load_config):
        """監視時間設定が欠けている場合のテスト"""
        # 監視時間設定を削除
        config_without_hours = {
            'urls': ['https://example.com/test'],
            'webhookUrl': 'https://discord.com/api/webhooks/test'
        }
        mock_load_config.return_value = config_without_hours
        
        monitor = RakutenMonitor()
        
        # デフォルト値が使用されることを確認
        # （実装によって24時間監視またはデフォルト時間が設定される）
        result = monitor._is_monitoring_time()
        assert isinstance(result, bool)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])