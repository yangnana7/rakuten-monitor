#!/usr/bin/env python3
"""PostgreSQL統合テスト用スクリプト"""

import sys
import os

# 相対インポートを回避するためパスを追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from item_db import ItemDB

logging.basicConfig(level=logging.INFO)

def test_postgresql_integration():
    """PostgreSQL統合テスト"""
    print("=== PostgreSQL 統合テスト ===")
    
    try:
        # 接続テスト
        with ItemDB() as db:
            print("✅ PostgreSQL接続成功")
            
            # テストデータの挿入
            test_item = {
                'item_code': 'test_001',
                'title': 'テスト商品',
                'price': 1000,
                'status': '在庫あり'
            }
            
            db.save_item(test_item)
            print("✅ テストデータ挿入成功")
            
            # データ取得テスト
            retrieved_item = db.get_item('test_001')
            if retrieved_item and retrieved_item['title'] == 'テスト商品':
                print("✅ データ取得成功")
            else:
                print("❌ データ取得失敗")
                return False
            
            # ステータス更新テスト
            db.update_status('test_001', '売り切れ')
            updated_item = db.get_item('test_001')
            if updated_item and updated_item['status'] == '売り切れ':
                print("✅ ステータス更新成功")
            else:
                print("❌ ステータス更新失敗")
                return False
            
            # 全データ取得テスト
            all_items = db.get_all_items()
            print(f"✅ 全データ取得成功 ({len(all_items)}件)")
            
            print("\n🎉 PostgreSQL統合テストすべて成功")
            return True
            
    except Exception as e:
        print(f"❌ PostgreSQL統合テスト失敗: {e}")
        return False

if __name__ == '__main__':
    success = test_postgresql_integration()
    sys.exit(0 if success else 1)