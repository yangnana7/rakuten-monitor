#!/usr/bin/env python3
"""SQLiteデータベースのダンプ作成スクリプト"""

import sqlite3

def dump_sqlite_database(db_path, output_path):
    """SQLiteデータベースをSQLダンプファイルに出力"""
    conn = sqlite3.connect(db_path)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in conn.iterdump():
            f.write(line + '\n')
    
    conn.close()
    print(f"SQLiteダンプを '{output_path}' に作成しました")

if __name__ == '__main__':
    dump_sqlite_database('products.sqlite', '/tmp/products.sql')