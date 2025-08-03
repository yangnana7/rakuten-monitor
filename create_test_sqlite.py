#!/usr/bin/env python3
"""テスト用SQLiteデータベース作成スクリプト"""

import sqlite3
from datetime import datetime

def create_test_database():
    """テスト用のSQLiteデータベースを作成"""
    conn = sqlite3.connect('products.sqlite')
    cursor = conn.cursor()
    
    # テーブル作成
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            product_id TEXT NOT NULL,
            name TEXT NOT NULL,
            price TEXT,
            status TEXT NOT NULL,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(url, product_id)
        )
    """)
    
    # テストデータ挿入
    test_data = [
        ('https://item.rakuten.co.jp/shop/item1/', 'item1', 'テスト商品1', '1000円', '在庫あり', '2024-01-01 10:00:00', '2024-01-01 10:00:00'),
        ('https://item.rakuten.co.jp/shop/item2/', 'item2', 'テスト商品2', '2000円', '売り切れ', '2024-01-01 11:00:00', '2024-01-01 11:00:00'),
        ('https://item.rakuten.co.jp/shop/item3/', 'item3', 'テスト商品3', '3500円', '在庫あり', '2024-01-01 12:00:00', '2024-01-01 12:00:00'),
        ('https://item.rakuten.co.jp/shop/item4/', 'item4', 'テスト商品4', '500円', '在庫わずか', '2024-01-01 13:00:00', '2024-01-01 13:00:00'),
    ]
    
    cursor.executemany("""
        INSERT INTO items (url, product_id, name, price, status, first_seen, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, test_data)
    
    conn.commit()
    conn.close()
    print("テスト用SQLiteデータベース 'products.sqlite' を作成しました")
    print(f"レコード数: {len(test_data)}")

if __name__ == '__main__':
    create_test_database()