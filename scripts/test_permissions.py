#!/usr/bin/env python3
"""PostgreSQL権限確認スクリプト"""

import os
import sys

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from item_db import ItemDB

def test_postgresql_permissions():
    """PostgreSQL権限とテーブル作成をテスト"""
    print("🔍 PostgreSQL権限テスト開始...")
    
    try:
        with ItemDB() as db:
            print("✅ PostgreSQL接続成功")
            
            # データベース情報確認
            with db.connection.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_user;")
                db_name, user = cursor.fetchone()
                print(f"📊 接続情報: {db_name} as {user}")
                
                # テーブル一覧確認
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name;
                """)
                tables = [row[0] for row in cursor.fetchall()]
                print(f"📋 既存テーブル: {tables}")
                
                # itemsテーブル確認/作成テスト
                try:
                    cursor.execute("SELECT COUNT(*) FROM items;")
                    count = cursor.fetchone()[0]
                    print(f"✅ itemsテーブル: {count}件のレコード")
                except Exception as e:
                    print(f"ℹ️  itemsテーブル未作成: {e}")
                
                # 基本的なCRUD操作テスト
                print("\n🧪 基本操作テスト:")
                
                # テストデータ挿入
                test_item = {
                    'product_id': 'test_permission_check',
                    'name': '権限テスト商品',
                    'price': '1000円',
                    'status': 'available',
                    'url': 'https://test.example.com'
                }
                
                try:
                    db.save_item(test_item)
                    print("✅ INSERT権限: OK")
                    
                    # データ取得テスト
                    retrieved = db.get_item('test_permission_check')
                    if retrieved:
                        print("✅ SELECT権限: OK")
                        
                        # データ更新テスト
                        db.update_status('test_permission_check', 'out_of_stock')
                        print("✅ UPDATE権限: OK")
                        
                        # クリーンアップ
                        cursor.execute("DELETE FROM items WHERE product_id = %s", ('test_permission_check',))
                        db.connection.commit()
                        print("✅ DELETE権限: OK")
                    
                except Exception as e:
                    print(f"❌ CRUD操作エラー: {e}")
                
                print("\n🎉 PostgreSQL権限テスト完了!")
                
    except Exception as e:
        print(f"❌ PostgreSQL権限テスト失敗: {e}")
        return False
    
    return True

if __name__ == "__main__":
    # 環境変数確認
    if not os.getenv('PGPASSWORD'):
        print("⚠️  PGPASSWORD環境変数が未設定です")
        print("実行前に: export PGPASSWORD='7856'")
        exit(1)
    
    success = test_postgresql_permissions()
    exit(0 if success else 1)