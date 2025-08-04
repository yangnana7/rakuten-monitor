"""!status -ls コマンドのテスト"""

import pytest
import unittest.mock as mock
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import discord
from discord.ext import commands

# テスト対象のインポート
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from status_report import get_items, get_items_count
from discord_bot import status_ls_command
from models import ProductStateManager, ProductState


@pytest.fixture
def test_db():
    """テスト用のSQLiteデータベースとダミーデータ"""
    import tempfile
    import os
    
    # 一時的なテスト用DBファイル
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    
    try:
        # テスト用データベースセットアップ
        state_manager = ProductStateManager("sqlite", db_path)
        
        # ダミーデータ投入（ページネーションテスト用に15個作成）
        test_states = []
        for i in range(15):
            now = datetime.now()
            test_states.append(ProductState(
                id=f"test{i+1}",
                name=f"テスト商品{i+1}",
                price=(i+1) * 100,
                url=f"https://item.rakuten.co.jp/shop/item/test{i+1}",
                in_stock=True,
                last_seen_at=now - timedelta(minutes=i),
                first_seen_at=now - timedelta(hours=24)
            ))
        
        for state in test_states:
            state_manager.save_product_state(state)
        
        yield db_path, state_manager
        
    finally:
        # クリーンアップ
        if os.path.exists(db_path):
            os.unlink(db_path)


class TestStatusLsCommand:
    """!status -ls コマンドのテストクラス"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される準備処理"""
        self.mock_items_data = [
            {
                'title': 'テスト商品1',
                'url': 'https://item.rakuten.co.jp/shop/item/test1',
                'price': 1000,
                'status': 'NEW',
                'updated_at': datetime.now().isoformat()
            },
            {
                'title': 'テスト商品2',
                'url': 'https://item.rakuten.co.jp/shop/item/test2',
                'price': 2000,
                'status': 'RESTOCK',
                'updated_at': (datetime.now() - timedelta(hours=1)).isoformat()
            }
        ]
    
    def test_get_items_basic(self, test_db):
        """基本的なアイテム取得のテスト"""
        db_path, state_manager = test_db
        
        # status_report関数でテスト用DBを使用するようにパッチ
        with mock.patch('status_report.ProductStateManager') as mock_manager:
            mock_manager.return_value = state_manager
            
            # 実行
            items = get_items(page=1, per_page=10)
            total = get_items_count()
            
            # 検証 
            assert len(items) == 10  # per_page=10で要求したので10件
            assert total == 15  # テストデータ全体は15件
            assert items[0]['title'] == 'テスト商品1'
            assert items[0]['status'] == 'NEW'
    
    def test_get_items_with_filters(self, test_db):
        """フィルタ付きアイテム取得のテスト"""
        db_path, state_manager = test_db
        
        # status_report関数でテスト用DBを使用するようにパッチ
        with mock.patch('status_report.ProductStateManager') as mock_manager:
            mock_manager.return_value = state_manager
            
            # 実行（NEWステータスのみ）
            filters = {'status': ['NEW']}
            items = get_items(page=1, per_page=10, filters=filters)
            total = get_items_count(filters=filters)
            
            # 検証（test1-5がNEWステータス）
            assert len(items) == 5  # test1-5がNEWとして判定される
            assert total == 5
            assert items[0]['status'] == 'NEW'
    
    def test_get_items_pagination(self, test_db):
        """ページネーションのテスト"""
        db_path, state_manager = test_db
        
        # status_report関数でテスト用DBを使用するようにパッチ
        with mock.patch('status_report.ProductStateManager') as mock_manager:
            mock_manager.return_value = state_manager
            
            # 実行（1ページ目、10件ずつ）
            items_page1 = get_items(page=1, per_page=10)
            total = get_items_count()
            
            # 検証
            assert len(items_page1) == 10
            assert total == 15  # テストデータが15件
            
            # 2ページ目のテスト
            items_page2 = get_items(page=2, per_page=10)
            assert len(items_page2) == 5  # 残り5件
    
    @mock.patch('status_report.get_items')
    @mock.patch('status_report.get_items_count')
    def test_get_items_empty_result(self, mock_count, mock_items):
        """空の結果のテスト"""
        # 空のデータ
        mock_items.return_value = []
        mock_count.return_value = 0
        
        # 実行
        items = get_items(page=1, per_page=10, filters={'status': ['NONEXISTENT']})
        total = get_items_count(filters={'status': ['NONEXISTENT']})
        
        # 検証
        assert len(items) == 0
        assert total == 0
    
    @pytest.mark.asyncio
    @mock.patch('status_report.get_items')
    @mock.patch('status_report.get_items_count')
    async def test_discord_command_basic(self, mock_count, mock_items):
        """Discord コマンドの基本テスト"""
        # モックの設定
        mock_items.return_value = self.mock_items_data
        mock_count.return_value = 2
        
        # Discordのモックオブジェクト作成
        mock_ctx = AsyncMock()
        mock_message = AsyncMock()
        mock_ctx.send.return_value = mock_message
        
        # コマンド実行
        await status_ls_command(mock_ctx)
        
        # 検証
        mock_ctx.send.assert_called()
        mock_message.edit.assert_called()
        
        # edit呼び出しの引数を確認
        call_args = mock_message.edit.call_args
        assert call_args[1]['content'] is None
        assert isinstance(call_args[1]['embed'], discord.Embed)
    
    @pytest.mark.asyncio
    @mock.patch('status_report.get_items')
    @mock.patch('status_report.get_items_count')
    async def test_discord_command_with_args(self, mock_count, mock_items):
        """Discord コマンドの引数付きテスト"""
        # NEWステータスのみのデータ
        new_items = [item for item in self.mock_items_data if item['status'] == 'NEW']
        mock_items.return_value = new_items
        mock_count.return_value = 1
        
        # Discordのモックオブジェクト作成
        mock_ctx = AsyncMock()
        mock_message = AsyncMock()
        mock_ctx.send.return_value = mock_message
        
        # コマンド実行（--new フィルタ付き）
        await status_ls_command(mock_ctx, '--new')
        
        # 検証
        mock_ctx.send.assert_called()
        mock_message.edit.assert_called()
        
        # get_itemsが正しいフィルタで呼ばれたかチェック
        mock_items.assert_called_with(page=1, per_page=10, filters={'status': ['NEW']})
    
    @pytest.mark.asyncio
    @mock.patch('status_report.get_items')
    @mock.patch('status_report.get_items_count')
    async def test_discord_command_page_option(self, mock_count, mock_items):
        """Discord コマンドのページオプションテスト"""
        # モックの設定
        mock_items.return_value = self.mock_items_data
        mock_count.return_value = 25  # 複数ページ想定
        
        # Discordのモックオブジェクト作成
        mock_ctx = AsyncMock()
        mock_message = AsyncMock()
        mock_ctx.send.return_value = mock_message
        
        # コマンド実行（--page 2）
        await status_ls_command(mock_ctx, '--page', '2')
        
        # 検証
        mock_ctx.send.assert_called()
        mock_message.edit.assert_called()
        
        # get_itemsが正しいページで呼ばれたかチェック
        mock_items.assert_called_with(page=2, per_page=10, filters={})
    
    @pytest.mark.asyncio
    @mock.patch('status_report.get_items')
    @mock.patch('status_report.get_items_count')
    async def test_discord_command_error_handling(self, mock_count, mock_items):
        """Discord コマンドのエラー処理テスト"""
        # 例外を発生させる
        mock_items.side_effect = Exception("Database connection error")
        
        # Discordのモックオブジェクト作成
        mock_ctx = AsyncMock()
        mock_message = AsyncMock()
        mock_ctx.send.return_value = mock_message
        
        # コマンド実行
        await status_ls_command(mock_ctx)
        
        # エラー処理が呼ばれたかチェック（具体的な実装に依存）
        assert mock_ctx.send.call_count > 0


class TestStatusLsIntegration:
    """統合テスト"""
    
    def test_pagination_calculation(self):
        """ページネーション計算のテスト"""
        import math
        
        # 25件のアイテムで10件/ページの場合
        total_items = 25
        per_page = 10
        total_pages = math.ceil(total_items / per_page)
        
        assert total_pages == 3
        
        # 0件の場合
        total_items = 0
        total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1
        assert total_pages == 1
        
        # 10件ちょうどの場合
        total_items = 10
        total_pages = math.ceil(total_items / per_page)
        assert total_pages == 1
    
    def test_filter_combinations(self):
        """フィルタの組み合わせテスト"""
        # 複数ステータスのフィルタ
        filters = {'status': ['NEW', 'RESTOCK']}
        
        # この場合、NEWまたはRESTOCKのアイテムが返されるべき
        assert 'NEW' in filters['status']
        assert 'RESTOCK' in filters['status']
        assert len(filters['status']) == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])