#!/usr/bin/env python3
"""
monitor.py のテスト
"""

import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Item, Change, Run, ChangeType
from monitor import RakutenMonitor

class TestRakutenMonitor:
    def setup_method(self):
        """テストセットアップ - 一時的なSQLiteデータベースを作成"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        self.test_db_url = f"sqlite:///{self.temp_db.name}"
        
        # テスト用のデータベースエンジンとセッション
        self.engine = create_engine(self.test_db_url)
        Base.metadata.create_all(self.engine)
        
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # monitor.pyのSessionLocalをモック
        self.session_patcher = patch('monitor.SessionLocal', self.SessionLocal)
        self.session_patcher.start()
        
        # メトリクス関連をモック
        self.metrics_patcher = patch('monitor.metrics_server')
        self.mock_metrics = self.metrics_patcher.start()
        self.mock_metrics.start_server = MagicMock()
        
        # Discord通知をモック
        self.discord_patcher = patch('monitor.DiscordNotifier')
        self.mock_discord_class = self.discord_patcher.start()
        self.mock_discord = MagicMock()
        self.mock_discord_class.return_value = self.mock_discord

    def teardown_method(self):
        """テスト後片付け"""
        self.session_patcher.stop()
        self.metrics_patcher.stop()
        self.discord_patcher.stop()
        
        # 一時ファイル削除
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_monitor_init(self):
        """RakutenMonitor初期化テスト"""
        monitor = RakutenMonitor()
        
        assert monitor.db is not None
        assert monitor.discord_notifier is not None
        self.mock_metrics.start_server.assert_called_once()

    def test_save_run_metadata(self):
        """実行メタデータ保存テスト"""
        monitor = RakutenMonitor()
        
        fetched_at = datetime.now()
        snapshot_data = {"items": [{"code": "test1", "title": "Test Item"}]}
        
        run_id = monitor.save_run_metadata(fetched_at, snapshot_data)
        
        assert isinstance(run_id, int)
        assert run_id > 0
        
        # データベースに保存されているか確認
        db_run = monitor.db.query(Run).filter(Run.id == run_id).first()
        assert db_run is not None
        assert db_run.fetched_at == fetched_at

    def test_upsert_items_new_items(self):
        """新商品のUpsertテスト"""
        monitor = RakutenMonitor()
        
        items = [
            {"code": "item1", "title": "商品1", "price": 3980, "in_stock": True},
            {"code": "item2", "title": "商品2", "price": 5500, "in_stock": False}
        ]
        
        monitor.upsert_items(items)
        
        # データベースに保存されているか確認
        db_items = monitor.db.query(Item).all()
        assert len(db_items) == 2
        
        item1 = monitor.db.query(Item).filter(Item.code == "item1").first()
        assert item1.title == "商品1"
        assert item1.price == 3980
        assert item1.in_stock is True

    def test_upsert_items_update_existing(self):
        """既存商品の更新テスト"""
        monitor = RakutenMonitor()
        
        # 最初に商品を保存
        initial_items = [{"code": "item1", "title": "商品1", "price": 3980, "in_stock": True}]
        monitor.upsert_items(initial_items)
        
        # 同じ商品を更新
        updated_items = [{"code": "item1", "title": "商品1 - 更新版", "price": 4500, "in_stock": False}]
        monitor.upsert_items(updated_items)
        
        # 商品数は変わらず、内容が更新されていることを確認
        db_items = monitor.db.query(Item).all()
        assert len(db_items) == 1
        
        item1 = monitor.db.query(Item).filter(Item.code == "item1").first()
        assert item1.title == "商品1 - 更新版"
        assert item1.price == 4500
        assert item1.in_stock is False

    def test_save_changes(self):
        """変更データ保存テスト"""
        monitor = RakutenMonitor()
        
        changes = [
            {
                "type": "NEW",
                "code": "item1",
                "title": "新商品"
            },
            {
                "type": "PRICE_UPDATE",
                "code": "item2",
                "old_price": 3980,
                "new_price": 4500
            }
        ]
        
        monitor.save_changes(changes)
        
        # データベースに保存されているか確認
        db_changes = monitor.db.query(Change).all()
        assert len(db_changes) == 2
        
        # NEW変更
        new_change = monitor.db.query(Change).filter(
            Change.type == ChangeType.NEW
        ).first()
        assert new_change.code == "item1"
        
        # PRICE_UPDATE変更
        price_change = monitor.db.query(Change).filter(
            Change.type == ChangeType.PRICE_UPDATE
        ).first()
        assert price_change.code == "item2"
        assert price_change.payload is not None

    def test_get_previous_snapshot_no_data(self):
        """前回スナップショット取得テスト（データなし）"""
        monitor = RakutenMonitor()
        
        snapshot = monitor.get_previous_snapshot()
        
        assert snapshot == {"fetched_at": 0, "items": []}

    def test_get_previous_snapshot_with_data(self):
        """前回スナップショット取得テスト（データあり）"""
        monitor = RakutenMonitor()
        
        # テストデータを保存
        fetched_at = datetime.now()
        snapshot_data = {"items": [{"code": "test1", "title": "Test"}]}
        monitor.save_run_metadata(fetched_at, snapshot_data)
        
        # 前回スナップショットを取得
        previous = monitor.get_previous_snapshot()
        
        assert previous["items"] == [{"code": "test1", "title": "Test"}]
        assert previous["fetched_at"] == int(fetched_at.timestamp())

    @patch('monitor.parse_list')
    @patch('monitor.detect_changes')
    @patch('monitor.record_items_fetched')
    @patch('monitor.record_run_success')
    def test_run_monitoring_cycle_success(self, mock_record_success, mock_record_items, 
                                        mock_detect_changes, mock_parse_list):
        """監視サイクル実行成功テスト"""
        monitor = RakutenMonitor()
        
        # モックの設定
        mock_items = [{"code": "item1", "title": "商品1", "price": 3980, "in_stock": True}]
        mock_parse_list.return_value = mock_items
        mock_detect_changes.return_value = []
        
        result = monitor.run_monitoring_cycle()
        
        assert result["success"] is True
        assert result["items_count"] == 1
        assert result["changes_count"] == 0
        
        # メトリクス記録が呼ばれたか確認
        mock_record_items.assert_called_once_with(1)
        mock_record_success.assert_called_once()

    @patch('monitor.parse_list')
    @patch('monitor.record_run_failure')
    def test_run_monitoring_cycle_fetch_failure(self, mock_record_failure, mock_parse_list):
        """監視サイクル実行失敗テスト（取得失敗）"""
        monitor = RakutenMonitor()
        
        # 商品取得が失敗する場合
        mock_parse_list.return_value = []
        
        result = monitor.run_monitoring_cycle()
        
        assert result["success"] is False
        assert result["error"] == "No items fetched"
        mock_record_failure.assert_called_once()

    @patch('monitor.parse_list')
    @patch('monitor.detect_changes')
    @patch('monitor.record_discord_notification')
    def test_run_monitoring_cycle_with_changes(self, mock_record_discord, 
                                             mock_detect_changes, mock_parse_list):
        """監視サイクル実行テスト（変更あり）"""
        monitor = RakutenMonitor()
        
        # モックの設定
        mock_items = [{"code": "item1", "title": "商品1", "price": 3980, "in_stock": True}]
        mock_changes = [{"type": "NEW", "code": "item1", "title": "商品1"}]
        
        mock_parse_list.return_value = mock_items
        mock_detect_changes.return_value = mock_changes
        self.mock_discord.send_notification.return_value = True
        
        # 前回データを設定（変更検出のため）
        previous_data = {"items": []}
        monitor.save_run_metadata(datetime.now(), previous_data)
        
        result = monitor.run_monitoring_cycle()
        
        assert result["success"] is True
        assert result["changes_count"] == 1
        
        # Discord通知が呼ばれたか確認
        self.mock_discord.send_notification.assert_called_once_with(mock_changes)
        mock_record_discord.assert_called_once_with('change', True)

    @patch('monitor.parse_list')
    @patch('monitor.record_run_failure')
    def test_run_monitoring_cycle_exception_handling(self, mock_record_failure, mock_parse_list):
        """監視サイクル例外処理テスト"""
        monitor = RakutenMonitor()
        
        # 例外を発生させる
        mock_parse_list.side_effect = Exception("Network error")
        
        result = monitor.run_monitoring_cycle()
        
        assert result["success"] is False
        assert "Network error" in result["error"]
        mock_record_failure.assert_called_once()
        
        # エラー通知が送信されることを確認
        self.mock_discord.notify_error.assert_called_once()

    def test_close(self):
        """クローズ処理テスト"""
        monitor = RakutenMonitor()
        
        # エラーが発生しないことを確認
        monitor.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])