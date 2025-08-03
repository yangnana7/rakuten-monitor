"""PostgreSQL ItemDB のテスト"""

import pytest
import os
from unittest.mock import patch, MagicMock
from datetime import datetime
from item_db import ItemDB
from exceptions import DatabaseConnectionError


class TestItemDB:
    """ItemDBクラスのテスト"""
    
    @pytest.fixture(autouse=True)
    def setup_env(self):
        """テスト用環境変数設定"""
        env_vars = {
            'PGHOST': 'localhost',
            'PGPORT': '5432',
            'PGDATABASE': 'test_rakuten',
            'PGUSER': 'test_user',
            'PGPASSWORD': 'test_pass'
        }
        with patch.dict(os.environ, env_vars):
            yield
    
    def test_skip_if_no_postgres(self):
        """PostgreSQL環境が無い場合はテストをスキップ"""
        if not os.getenv('POSTGRES_TEST_ENABLED'):
            pytest.skip("PostgreSQL test environment not available")
    
    @patch('item_db.psycopg2.connect')
    def test_init_success(self, mock_connect):
        """正常な初期化テスト"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        db = ItemDB()
        
        mock_connect.assert_called_once()
        mock_cursor.execute.assert_called_once()
        assert db.connection == mock_conn
    
    @patch('item_db.psycopg2.connect')
    def test_init_connection_error(self, mock_connect):
        """接続エラーテスト"""
        mock_connect.side_effect = Exception("Connection failed")
        
        with pytest.raises(DatabaseConnectionError):
            ItemDB()
    
    @patch('item_db.psycopg2.connect')
    def test_context_manager(self, mock_connect):
        """コンテキストマネージャーテスト"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        with ItemDB() as db:
            assert db.connection == mock_conn
        
        mock_conn.close.assert_called_once()
    
    @patch('item_db.psycopg2.connect')
    def test_get_item_found(self, mock_connect):
        """商品取得（見つかった場合）テスト"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {
            'item_code': 'test_item',
            'title': 'テスト商品',
            'price': 1000,
            'status': '在庫あり'
        }
        mock_connect.return_value = mock_conn
        
        db = ItemDB()
        result = db.get_item('test_item')
        
        assert result['item_code'] == 'test_item'
        assert result['title'] == 'テスト商品'
    
    @patch('item_db.psycopg2.connect')
    def test_get_item_not_found(self, mock_connect):
        """商品取得（見つからない場合）テスト"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None
        mock_connect.return_value = mock_conn
        
        db = ItemDB()
        result = db.get_item('nonexistent_item')
        
        assert result is None
    
    @patch('item_db.psycopg2.connect')
    def test_save_item(self, mock_connect):
        """商品保存テスト"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        db = ItemDB()
        item_data = {
            'item_code': 'test_item',
            'title': 'テスト商品',
            'price': 1000,
            'status': '在庫あり'
        }
        
        db.save_item(item_data)
        
        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()
    
    @patch('item_db.psycopg2.connect')
    def test_update_status(self, mock_connect):
        """ステータス更新テスト"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        db = ItemDB()
        db.update_status('test_item', '売り切れ')
        
        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()
    
    @patch('item_db.psycopg2.connect')
    def test_get_all_items(self, mock_connect):
        """全商品取得テスト"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {'item_code': 'item1', 'title': '商品1'},
            {'item_code': 'item2', 'title': '商品2'}
        ]
        mock_connect.return_value = mock_conn
        
        db = ItemDB()
        results = db.get_all_items()
        
        assert len(results) == 2
        assert results[0]['item_code'] == 'item1'
    
    @patch('item_db.psycopg2.connect')
    def test_cleanup_old_items(self, mock_connect):
        """古いアイテム削除テスト"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.rowcount = 5
        mock_connect.return_value = mock_conn
        
        db = ItemDB()
        deleted_count = db.cleanup_old_items(30)
        
        assert deleted_count == 5
        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()


# 統合テスト（実際のPostgreSQLが必要）
@pytest.mark.integration
class TestItemDBIntegration:
    """ItemDBの統合テスト（実際のPostgreSQLが必要）"""
    
    def test_skip_integration_tests(self):
        """統合テスト環境が無い場合はスキップ"""
        if not os.getenv('POSTGRES_INTEGRATION_TEST_ENABLED'):
            pytest.skip("PostgreSQL integration test environment not available")
    
    def test_full_workflow(self):
        """完全なワークフローテスト"""
        # 実際のPostgreSQLを使用したテスト
        # 環境変数でテスト用DBを指定
        pass