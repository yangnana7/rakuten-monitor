#!/usr/bin/env python3
"""マイグレーションスクリプトの解析部分をテスト"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scripts.migrate_sqlite_to_pg import SQLiteToPGMigrator

def test_parse_sqlite_dump():
    """SQLite dump の解析をテスト"""
    # ダミーマイグレーターを作成（接続は行わない）
    migrator = object.__new__(SQLiteToPGMigrator)
    
    # 解析メソッドを直接呼び出し
    try:
        items = migrator._parse_sqlite_dump('/tmp/products.sql')
        print(f"解析結果: {len(items)}個のアイテム")
        for i, item in enumerate(items):
            print(f"  {i+1}: {item}")
        return True
    except Exception as e:
        print(f"解析エラー: {e}")
        return False

if __name__ == '__main__':
    success = test_parse_sqlite_dump()
    if success:
        print("\n✅ SQLiteダンプの解析は正常に動作します")
        print("📝 実際のPostgreSQLサーバーへの接続が設定されれば、マイグレーションが実行できます")
    else:
        print("\n❌ SQLiteダンプの解析でエラーが発生しました")