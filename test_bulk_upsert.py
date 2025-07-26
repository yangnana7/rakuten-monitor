#!/usr/bin/env python3
"""
Bulk Upsert機能のテスト・ベンチマーク
"""

import pytest
import tempfile
import os
import time
from unittest.mock import patch, MagicMock
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Item
from monitor import RakutenMonitor

class TestBulkUpsert:
    """Bulk Upsert機能のテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
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

    def test_bulk_upsert_sqlite_new_items(self):
        """SQLite bulk upsert - 新商品テスト"""
        monitor = RakutenMonitor()
        
        items = [
            {"code": "item1", "title": "商品1", "price": 1000, "in_stock": True},
            {"code": "item2", "title": "商品2", "price": 2000, "in_stock": False},
            {"code": "item3", "title": "商品3", "price": 3000, "in_stock": True}
        ]
        
        monitor.upsert_items(items)
        
        # データベースに保存されているか確認
        db_items = monitor.db.query(Item).all()
        assert len(db_items) == 3
        
        # 各商品の内容確認
        codes = [item.code for item in db_items]
        assert "item1" in codes
        assert "item2" in codes
        assert "item3" in codes

    def test_bulk_upsert_sqlite_update_existing(self):
        """SQLite bulk upsert - 既存商品更新テスト"""
        monitor = RakutenMonitor()
        
        # 初期データ投入
        initial_items = [
            {"code": "item1", "title": "商品1", "price": 1000, "in_stock": True},
            {"code": "item2", "title": "商品2", "price": 2000, "in_stock": True}
        ]
        monitor.upsert_items(initial_items)
        
        # 更新データ
        updated_items = [
            {"code": "item1", "title": "商品1（更新）", "price": 1500, "in_stock": False},
            {"code": "item2", "title": "商品2", "price": 2000, "in_stock": True},
            {"code": "item3", "title": "商品3（新規）", "price": 3000, "in_stock": True}
        ]
        
        monitor.upsert_items(updated_items)
        
        # 結果確認
        db_items = monitor.db.query(Item).all()
        assert len(db_items) == 3
        
        # 更新されたデータの確認
        item1 = monitor.db.query(Item).filter(Item.code == "item1").first()
        assert item1.title == "商品1（更新）"
        assert item1.price == 1500
        assert item1.in_stock is False
        
        # first_seenは保持、last_seenは更新されることを確認
        assert item1.first_seen is not None
        assert item1.last_seen is not None

    def test_bulk_upsert_empty_list(self):
        """空リストのupsertテスト"""
        monitor = RakutenMonitor()
        
        # 空リストでエラーが発生しないことを確認
        monitor.upsert_items([])
        
        # データベースが空であることを確認
        db_items = monitor.db.query(Item).all()
        assert len(db_items) == 0

    @patch('monitor.record_upsert_operation')
    @patch('monitor.record_database_operation')
    def test_metrics_recording(self, mock_db_op, mock_upsert_op):
        """メトリクス記録のテスト"""
        monitor = RakutenMonitor()
        
        items = [
            {"code": "item1", "title": "商品1", "price": 1000, "in_stock": True}
        ]
        
        monitor.upsert_items(items)
        
        # メトリクス記録が呼ばれたことを確認
        mock_db_op.assert_called_with('bulk_upsert', True)
        mock_upsert_op.assert_called()
        
        # upsert_operationの引数確認
        args, kwargs = mock_upsert_op.call_args
        assert args[0] == 'sqlite'  # database_type
        assert args[1] == 1         # items_count
        assert isinstance(args[2], float)  # duration

    def test_database_type_detection(self):
        """データベースタイプ検出のテスト"""
        monitor = RakutenMonitor()
        
        # SQLiteの場合
        assert 'sqlite' in str(monitor.db.bind.url)
        
        # PostgreSQL URLでのテスト（モック）
        with patch.object(monitor.db, 'bind') as mock_bind:
            mock_bind.url = 'postgresql://user:pass@localhost/db'
            
            items = [{"code": "test", "title": "test", "price": 100, "in_stock": True}]
            
            # PostgreSQL用のメソッドが呼ばれることを確認
            with patch.object(monitor, '_bulk_upsert_postgresql') as mock_pg:
                with patch.object(monitor, '_bulk_upsert_sqlite') as mock_sqlite:
                    monitor.upsert_items(items)
                    mock_pg.assert_called_once()
                    mock_sqlite.assert_not_called()

    def test_error_handling(self):
        """エラーハンドリングのテスト"""
        monitor = RakutenMonitor()
        
        # 不正なデータでエラーが発生することを確認
        invalid_items = [
            {"code": None, "title": "不正な商品", "price": "無効な価格", "in_stock": True}
        ]
        
        with pytest.raises(Exception):
            monitor.upsert_items(invalid_items)

    @pytest.mark.benchmark
    def test_performance_comparison(self):
        """パフォーマンス比較テスト"""
        monitor = RakutenMonitor()
        
        # 大量データの準備（100商品）
        items = []
        for i in range(100):
            items.append({
                "code": f"perf-item-{i}",
                "title": f"パフォーマンステスト商品{i}",
                "price": 1000 + i * 10,
                "in_stock": i % 2 == 0
            })
        
        # Bulk upsertのタイミング測定
        start_time = time.time()
        monitor.upsert_items(items)
        bulk_duration = time.time() - start_time
        
        print(f"Bulk upsert duration for 100 items: {bulk_duration:.3f}s")
        
        # 結果検証
        db_items = monitor.db.query(Item).all()
        assert len(db_items) == 100
        
        # パフォーマンスが許容範囲内であることを確認（5秒以内）
        assert bulk_duration < 5.0

    def test_first_seen_preservation(self):
        """first_seen保持のテスト"""
        monitor = RakutenMonitor()
        
        # 初回挿入
        initial_time = datetime.now()
        items = [{"code": "preserve-test", "title": "保持テスト", "price": 1000, "in_stock": True}]
        monitor.upsert_items(items)
        
        # first_seenを取得
        item = monitor.db.query(Item).filter(Item.code == "preserve-test").first()
        original_first_seen = item.first_seen
        
        # 少し時間をおいて更新
        time.sleep(0.1)
        updated_items = [{"code": "preserve-test", "title": "保持テスト（更新）", "price": 1100, "in_stock": False}]
        monitor.upsert_items(updated_items)
        
        # first_seenが保持されていることを確認
        updated_item = monitor.db.query(Item).filter(Item.code == "preserve-test").first()
        assert updated_item.first_seen == original_first_seen
        assert updated_item.last_seen > original_first_seen
        assert updated_item.title == "保持テスト（更新）"
        assert updated_item.price == 1100

    def test_mixed_operations(self):
        """新規・更新混在のテスト"""
        monitor = RakutenMonitor()
        
        # 初期データ
        initial_items = [
            {"code": "existing1", "title": "既存商品1", "price": 1000, "in_stock": True},
            {"code": "existing2", "title": "既存商品2", "price": 2000, "in_stock": True}
        ]
        monitor.upsert_items(initial_items)
        
        # 新規・更新混在
        mixed_items = [
            {"code": "existing1", "title": "既存商品1（更新）", "price": 1200, "in_stock": False},  # 更新
            {"code": "existing2", "title": "既存商品2", "price": 2000, "in_stock": True},          # 変更なし
            {"code": "new1", "title": "新商品1", "price": 3000, "in_stock": True},                # 新規
            {"code": "new2", "title": "新商品2", "price": 4000, "in_stock": False}               # 新規
        ]
        
        monitor.upsert_items(mixed_items)
        
        # 結果確認
        db_items = monitor.db.query(Item).all()
        assert len(db_items) == 4
        
        # 個別確認
        existing1 = monitor.db.query(Item).filter(Item.code == "existing1").first()
        assert existing1.title == "既存商品1（更新）"
        assert existing1.price == 1200
        
        new1 = monitor.db.query(Item).filter(Item.code == "new1").first()
        assert new1.title == "新商品1"
        assert new1.price == 3000

if __name__ == "__main__":
    pytest.main([__file__, "-v"])