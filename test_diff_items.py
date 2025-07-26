#!/usr/bin/env python3
"""
diff_items.py のテスト
"""

import pytest
from diff_items import detect_changes

class TestDetectChanges:
    def test_detect_new_items(self):
        """新商品検出のテスト"""
        current = {
            "items": [
                {"code": "item1", "title": "商品1", "price": 3980, "in_stock": True},
                {"code": "item2", "title": "商品2", "price": 5500, "in_stock": True}
            ]
        }
        previous = {
            "items": [
                {"code": "item1", "title": "商品1", "price": 3980, "in_stock": True}
            ]
        }
        
        changes = detect_changes(current, previous)
        
        assert len(changes) == 1
        assert changes[0]["type"] == "NEW"
        assert changes[0]["code"] == "item2"
        assert changes[0]["title"] == "商品2"

    def test_detect_restock(self):
        """再入荷検出のテスト"""
        current = {
            "items": [
                {"code": "item1", "title": "商品1", "price": 3980, "in_stock": True}
            ]
        }
        previous = {
            "items": [
                {"code": "item1", "title": "商品1", "price": 3980, "in_stock": False}
            ]
        }
        
        changes = detect_changes(current, previous)
        
        assert len(changes) == 1
        assert changes[0]["type"] == "RESTOCK"
        assert changes[0]["code"] == "item1"

    def test_detect_soldout(self):
        """売り切れ検出のテスト"""
        current = {
            "items": [
                {"code": "item1", "title": "商品1", "price": 3980, "in_stock": False}
            ]
        }
        previous = {
            "items": [
                {"code": "item1", "title": "商品1", "price": 3980, "in_stock": True}
            ]
        }
        
        changes = detect_changes(current, previous)
        
        assert len(changes) == 1
        assert changes[0]["type"] == "SOLDOUT"
        assert changes[0]["code"] == "item1"

    def test_detect_price_update(self):
        """価格変更検出のテスト"""
        current = {
            "items": [
                {"code": "item1", "title": "商品1", "price": 4500, "in_stock": True}
            ]
        }
        previous = {
            "items": [
                {"code": "item1", "title": "商品1", "price": 3980, "in_stock": True}
            ]
        }
        
        changes = detect_changes(current, previous)
        
        assert len(changes) == 1
        assert changes[0]["type"] == "PRICE_UPDATE"
        assert changes[0]["code"] == "item1" 
        assert changes[0]["old_price"] == 3980
        assert changes[0]["new_price"] == 4500

    def test_detect_title_update(self):
        """タイトル変更検出のテスト"""
        current = {
            "items": [
                {"code": "item1", "title": "商品1 - 新バージョン", "price": 3980, "in_stock": True}
            ]
        }
        previous = {
            "items": [
                {"code": "item1", "title": "商品1", "price": 3980, "in_stock": True}
            ]
        }
        
        changes = detect_changes(current, previous)
        
        assert len(changes) == 1
        assert changes[0]["type"] == "TITLE_UPDATE"
        assert changes[0]["code"] == "item1"
        assert changes[0]["old_title"] == "商品1"
        assert changes[0]["new_title"] == "商品1 - 新バージョン"

    def test_no_changes(self):
        """変更なしのテスト"""
        current = {
            "items": [
                {"code": "item1", "title": "商品1", "price": 3980, "in_stock": True}
            ]
        }
        previous = {
            "items": [
                {"code": "item1", "title": "商品1", "price": 3980, "in_stock": True}
            ]
        }
        
        changes = detect_changes(current, previous)
        
        assert len(changes) == 0

    def test_multiple_changes(self):
        """複数変更のテスト"""
        current = {
            "items": [
                {"code": "item1", "title": "商品1", "price": 4500, "in_stock": True},  # 価格変更
                {"code": "item2", "title": "商品2", "price": 5500, "in_stock": True},  # 再入荷
                {"code": "item3", "title": "商品3", "price": 2980, "in_stock": True}   # 新商品
            ]
        }
        previous = {
            "items": [
                {"code": "item1", "title": "商品1", "price": 3980, "in_stock": True},
                {"code": "item2", "title": "商品2", "price": 5500, "in_stock": False}
            ]
        }
        
        changes = detect_changes(current, previous)
        
        assert len(changes) == 3
        
        # 変更タイプをチェック
        change_types = [change["type"] for change in changes]
        assert "PRICE_UPDATE" in change_types
        assert "RESTOCK" in change_types
        assert "NEW" in change_types

    def test_empty_current_items(self):
        """現在の商品リストが空の場合のテスト"""
        current = {"items": []}
        previous = {
            "items": [
                {"code": "item1", "title": "商品1", "price": 3980, "in_stock": True}
            ]
        }
        
        changes = detect_changes(current, previous)
        
        # 商品が消えた場合の処理（実装によっては売り切れとして扱う）
        assert isinstance(changes, list)

    def test_empty_previous_items(self):
        """前回の商品リストが空の場合のテスト"""
        current = {
            "items": [
                {"code": "item1", "title": "商品1", "price": 3980, "in_stock": True}
            ]
        }
        previous = {"items": []}
        
        changes = detect_changes(current, previous)
        
        assert len(changes) == 1
        assert changes[0]["type"] == "NEW"

    def test_complex_scenario(self):
        """複雑なシナリオのテスト"""
        current = {
            "items": [
                {"code": "item1", "title": "商品1 - 改良版", "price": 4200, "in_stock": True},  # タイトルと価格変更
                {"code": "item2", "title": "商品2", "price": 5500, "in_stock": False},           # 売り切れ
                {"code": "item4", "title": "商品4", "price": 7800, "in_stock": True}            # 新商品
            ]
        }
        previous = {
            "items": [
                {"code": "item1", "title": "商品1", "price": 3980, "in_stock": True},
                {"code": "item2", "title": "商品2", "price": 5500, "in_stock": True},
                {"code": "item3", "title": "商品3", "price": 2980, "in_stock": True}
            ]
        }
        
        changes = detect_changes(current, previous)
        
        # 変更が複数検出されることを確認
        assert len(changes) >= 3
        
        # 各種変更タイプが含まれることを確認
        change_types = [change["type"] for change in changes]
        assert "TITLE_UPDATE" in change_types or "PRICE_UPDATE" in change_types
        assert "SOLDOUT" in change_types  
        assert "NEW" in change_types

if __name__ == "__main__":
    pytest.main([__file__, "-v"])