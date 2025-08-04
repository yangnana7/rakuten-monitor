"""監視差分検出のテスト（BDDシナリオ3&4対応）"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from html_parser import Product
from models import ProductState, ProductStateManager, detect_changes, DiffResult


class TestDetectChanges:
    """detect_changes関数のテスト（BDDシナリオ対応）"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される準備処理"""
        # インメモリSQLiteを使用
        self.state_manager = ProductStateManager("sqlite", ":memory:")
        
        # テストデータの作成
        self.existing_product_in_stock = Product(
            id="existing_in_stock",
            name="既存在庫あり商品",
            price=1000,
            url="https://example.com/existing1",
            in_stock=True
        )
        
        self.existing_product_out_of_stock = Product(
            id="existing_out_of_stock", 
            name="既存売り切れ商品",
            price=2000,
            url="https://example.com/existing2",
            in_stock=False
        )
        
        self.new_product = Product(
            id="new_product",
            name="新商品",
            price=3000,
            url="https://example.com/new",
            in_stock=True
        )
        
        # 既存商品の状態を保存
        past_time = datetime.now() - timedelta(hours=1)
        
        existing_state1 = ProductState(
            id="existing_in_stock",
            url="https://example.com/existing1",
            name="既存在庫あり商品",
            price=1000,
            in_stock=True,
            last_seen_at=past_time,
            first_seen_at=past_time - timedelta(days=1),
            stock_change_count=0,
            price_change_count=0
        )
        
        existing_state2 = ProductState(
            id="existing_out_of_stock",
            url="https://example.com/existing2", 
            name="既存売り切れ商品",
            price=2000,
            in_stock=False,  # 売り切れ状態
            last_seen_at=past_time,
            first_seen_at=past_time - timedelta(days=2),
            stock_change_count=1,
            price_change_count=0
        )
        
        self.state_manager.save_product_state(existing_state1)
        self.state_manager.save_product_state(existing_state2)
    
    def test_scenario_3_new_product_detection(self):
        """BDDシナリオ3: 新商品の検知"""
        # 前回存在しなかった「在庫あり」商品を検出
        current_products = [
            self.existing_product_in_stock,  # 既存商品（変更なし）
            self.new_product                 # 新商品（在庫あり）
        ]
        
        # 差分検出実行
        diff_result = detect_changes(current_products, self.state_manager)
        
        # 検証: 新商品が検出される
        assert len(diff_result.new_items) == 1
        assert diff_result.new_items[0].id == "new_product"
        assert diff_result.new_items[0].name == "新商品"
        assert diff_result.new_items[0].in_stock == True
        
        # 他の変更がないことを確認
        assert len(diff_result.restocked) == 0
        assert len(diff_result.out_of_stock) == 0
        assert len(diff_result.price_changed) == 0
        
        # 新商品の状態が保存されていることを確認
        saved_state = self.state_manager.get_product_state("new_product")
        assert saved_state is not None
        assert saved_state.name == "新商品"
        assert saved_state.in_stock == True
    
    def test_scenario_4_restock_detection(self):
        """BDDシナリオ4: 再販（在庫復活）の検知"""
        # 売り切れ → 在庫あり に変わった商品を検出
        restocked_product = Product(
            id="existing_out_of_stock",  # 既存の売り切れ商品ID
            name="既存売り切れ商品",
            price=2000,
            url="https://example.com/existing2",
            in_stock=True  # 在庫復活！
        )
        
        current_products = [
            self.existing_product_in_stock,  # 既存商品（変更なし）
            restocked_product                # 再販商品
        ]
        
        # 差分検出実行
        diff_result = detect_changes(current_products, self.state_manager)
        
        # 検証: 再販が検出される
        assert len(diff_result.restocked) == 1
        assert diff_result.restocked[0].id == "existing_out_of_stock"
        assert diff_result.restocked[0].name == "既存売り切れ商品"
        assert diff_result.restocked[0].in_stock == True
        
        # 新商品としては検出されない
        assert len(diff_result.new_items) == 0
        
        # 状態が更新されていることを確認
        updated_state = self.state_manager.get_product_state("existing_out_of_stock")
        assert updated_state.in_stock == True
        assert updated_state.stock_change_count == 2  # 元々1回変更済み + 今回で2回
    
    def test_out_of_stock_detection(self):
        """売り切れ検知のテスト"""
        # 在庫あり → 売り切れ に変わった商品
        out_of_stock_product = Product(
            id="existing_in_stock",
            name="既存在庫あり商品", 
            price=1000,
            url="https://example.com/existing1",
            in_stock=False  # 売り切れに変更
        )
        
        current_products = [out_of_stock_product]
        
        # 差分検出実行
        diff_result = detect_changes(current_products, self.state_manager)
        
        # 検証: 売り切れが検出される
        assert len(diff_result.out_of_stock) == 1
        assert diff_result.out_of_stock[0].id == "existing_in_stock"
        assert diff_result.out_of_stock[0].in_stock == False
        
        # 状態が更新されていることを確認
        updated_state = self.state_manager.get_product_state("existing_in_stock")
        assert updated_state.in_stock == False
        assert updated_state.stock_change_count == 1
    
    def test_price_change_detection(self):
        """価格変更検知のテスト"""
        # 価格が変更された商品
        price_changed_product = Product(
            id="existing_in_stock",
            name="既存在庫あり商品",
            price=1500,  # 1000円 → 1500円に変更
            url="https://example.com/existing1",
            in_stock=True
        )
        
        current_products = [price_changed_product]
        
        # 差分検出実行
        diff_result = detect_changes(current_products, self.state_manager)
        
        # 検証: 価格変更が検出される
        assert len(diff_result.price_changed) == 1
        old_product, new_product = diff_result.price_changed[0]
        assert old_product.price == 1000
        assert new_product.price == 1500
        assert new_product.id == "existing_in_stock"
        
        # 状態が更新されていることを確認
        updated_state = self.state_manager.get_product_state("existing_in_stock")
        assert updated_state.price == 1500
        assert updated_state.price_change_count == 1
    
    def test_new_product_out_of_stock_not_notified(self):
        """新商品が売り切れの場合は通知されないことのテスト"""
        # 新商品だが売り切れ
        new_out_of_stock_product = Product(
            id="new_out_of_stock",
            name="新商品（売り切れ）",
            price=4000,
            url="https://example.com/new_out_of_stock",
            in_stock=False
        )
        
        current_products = [new_out_of_stock_product]
        
        # 差分検出実行
        diff_result = detect_changes(current_products, self.state_manager)
        
        # 検証: 新商品として通知されない（売り切れのため）
        assert len(diff_result.new_items) == 0
        
        # ただし、状態は保存される
        saved_state = self.state_manager.get_product_state("new_out_of_stock")
        assert saved_state is not None
        assert saved_state.in_stock == False
    
    def test_multiple_changes_scenario(self):
        """複数の変更が同時に発生するシナリオ"""
        # 新商品
        new_product = Product(
            id="multi_new",
            name="複数変更テスト新商品",
            price=5000,
            url="https://example.com/multi_new",
            in_stock=True
        )
        
        # 再販商品
        restocked_product = Product(
            id="existing_out_of_stock",
            name="既存売り切れ商品",
            price=2500,  # 価格も変更
            url="https://example.com/existing2",
            in_stock=True
        )
        
        # 売り切れ商品
        out_of_stock_product = Product(
            id="existing_in_stock",
            name="既存在庫あり商品",
            price=1000,
            url="https://example.com/existing1",
            in_stock=False
        )
        
        current_products = [new_product, restocked_product, out_of_stock_product]
        
        # 差分検出実行
        diff_result = detect_changes(current_products, self.state_manager)
        
        # 検証: 各変更が正しく検出される
        assert len(diff_result.new_items) == 1
        assert diff_result.new_items[0].id == "multi_new"
        
        assert len(diff_result.restocked) == 1
        assert diff_result.restocked[0].id == "existing_out_of_stock"
        
        assert len(diff_result.out_of_stock) == 1
        assert diff_result.out_of_stock[0].id == "existing_in_stock"
        
        # 価格変更も検出される（再販商品の価格が変更されている）
        assert len(diff_result.price_changed) == 1
        old_product, new_product = diff_result.price_changed[0]
        assert old_product.price == 2000
        assert new_product.price == 2500
    
    def test_no_changes_scenario(self):
        """変更がない場合のテスト"""
        # 既存商品のみで変更なし
        current_products = [
            self.existing_product_in_stock,
            self.existing_product_out_of_stock
        ]
        
        # 差分検出実行
        diff_result = detect_changes(current_products, self.state_manager)
        
        # 検証: 変更がないことを確認
        assert len(diff_result.new_items) == 0
        assert len(diff_result.restocked) == 0
        assert len(diff_result.out_of_stock) == 0
        assert len(diff_result.price_changed) == 0
        assert len(diff_result.updated_items) == 0


class TestDiffResult:
    """DiffResultデータクラスのテスト"""
    
    def test_diff_result_creation(self):
        """DiffResultオブジェクトの作成テスト"""
        product = Product(id="test", name="テスト", price=100, url="http://test.com", in_stock=True)
        
        diff_result = DiffResult(
            new_items=[product],
            restocked=[],
            out_of_stock=[],
            price_changed=[],
            updated_items=[]
        )
        
        assert len(diff_result.new_items) == 1
        assert len(diff_result.restocked) == 0
        assert len(diff_result.out_of_stock) == 0
        assert len(diff_result.price_changed) == 0
        assert len(diff_result.updated_items) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])