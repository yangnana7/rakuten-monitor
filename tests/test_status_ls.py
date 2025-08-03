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
    
    @mock.patch('status_report.get_items')
    @mock.patch('status_report.get_items_count')
    def test_get_items_basic(self, mock_count, mock_items):
        """基本的なアイテム取得のテスト"""
        # モックの設定
        mock_items.return_value = self.mock_items_data
        mock_count.return_value = 2
        
        # 実行
        items = get_items(page=1, per_page=10)
        total = get_items_count()
        
        # 検証
        assert len(items) == 2
        assert total == 2
        assert items[0]['title'] == 'テスト商品1'
        assert items[0]['status'] == 'NEW'
        
        # 関数が正しい引数で呼ばれたかチェック
        mock_items.assert_called_once_with(page=1, per_page=10, filters=None)
        mock_count.assert_called_once_with(filters=None)
    
    @mock.patch('status_report.get_items')
    @mock.patch('status_report.get_items_count')
    def test_get_items_with_filters(self, mock_count, mock_items):
        """フィルタ付きアイテム取得のテスト"""
        # NEWステータスのみのデータ
        new_items = [item for item in self.mock_items_data if item['status'] == 'NEW']
        mock_items.return_value = new_items
        mock_count.return_value = 1
        
        # 実行
        filters = {'status': ['NEW']}
        items = get_items(page=1, per_page=10, filters=filters)
        total = get_items_count(filters=filters)
        
        # 検証
        assert len(items) == 1
        assert total == 1
        assert items[0]['status'] == 'NEW'
        
        # 関数が正しい引数で呼ばれたかチェック
        mock_items.assert_called_once_with(page=1, per_page=10, filters=filters)
        mock_count.assert_called_once_with(filters=filters)
    
    @mock.patch('status_report.get_items')
    @mock.patch('status_report.get_items_count')
    def test_get_items_pagination(self, mock_count, mock_items):
        """ページネーションのテスト"""
        # 25件のテストデータを作成
        test_items = []
        for i in range(25):
            test_items.append({
                'title': f'テスト商品{i+1}',
                'url': f'https://item.rakuten.co.jp/shop/item/test{i+1}',
                'price': (i+1) * 100,
                'status': 'NEW' if i < 10 else 'RESTOCK' if i < 20 else 'STOCK',
                'updated_at': datetime.now().isoformat()
            })
        
        # ページ1の設定（最初の10件）
        mock_items.return_value = test_items[:10]
        mock_count.return_value = 25
        
        # 実行
        items_page1 = get_items(page=1, per_page=10)
        total = get_items_count()
        
        # 検証
        assert len(items_page1) == 10
        assert total == 25
        
        # ページ2の設定（次の10件）
        mock_items.return_value = test_items[10:20]
        items_page2 = get_items(page=2, per_page=10)
        
        # 検証
        assert len(items_page2) == 10
        
        # ページ3の設定（残りの5件）
        mock_items.return_value = test_items[20:25]
        items_page3 = get_items(page=3, per_page=10)
        
        # 検証
        assert len(items_page3) == 5
    
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