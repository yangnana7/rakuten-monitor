#!/usr/bin/env python3
"""SQLite dump から PostgreSQL へのマイグレーションスクリプト"""

import argparse
import os
import re
import logging
from typing import List, Tuple
import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SQLiteToPGMigrator:
    """SQLite dump から PostgreSQL への移行を行うクラス"""
    
    def __init__(self):
        self.connection = None
        self._connect()
    
    def _connect(self) -> None:
        """PostgreSQLに接続"""
        try:
            self.connection = psycopg2.connect(
                host=os.getenv('PGHOST', 'localhost'),
                port=os.getenv('PGPORT', '5432'),
                database=os.getenv('PGDATABASE', 'rakuten_monitor'),
                user=os.getenv('PGUSER', 'rakuten_user'),
                password=os.getenv('PGPASSWORD', 'rakuten_pass')
            )
            logger.info("PostgreSQL接続成功")
        except psycopg2.Error as e:
            logger.error(f"PostgreSQL接続に失敗: {e}")
            raise
    
    def _setup_table(self) -> None:
        """PostgreSQLにテーブルを作成"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS items (
                        item_code TEXT PRIMARY KEY,
                        title TEXT,
                        price INTEGER,
                        status TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                self.connection.commit()
                logger.info("テーブル作成完了")
        except psycopg2.Error as e:
            logger.error(f"テーブル作成に失敗: {e}")
            raise
    
    def _parse_sqlite_dump(self, dump_path: str) -> List[Tuple]:
        """SQLite dump ファイルを解析してデータを抽出"""
        items = []
        
        try:
            with open(dump_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # INSERT文を抽出（複数行対応、クオート付きテーブル名対応）
            insert_pattern = r'INSERT INTO ["\']?items["\']?\s+VALUES\s*\((.*?)\);'
            matches = re.findall(insert_pattern, content, re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                # VALUES内の値を解析
                values = self._parse_values(match)
                if len(values) >= 8:  # 元のSQLiteテーブルの列数
                    # PostgreSQL用に変換（id, url, product_id, name, price, status, first_seen, last_updated）
                    item_code = f"{values[1]}_{values[2]}"  # url + product_id をitem_codeに
                    title = values[3]  # name -> title
                    price = self._convert_price(values[4])  # price文字列を整数に変換
                    status = values[5]
                    updated_at = values[7]  # last_updated
                    
                    items.append((item_code, title, price, status, updated_at))
            
            logger.info(f"{len(items)}個のアイテムを解析しました")
            return items
            
        except FileNotFoundError:
            logger.error(f"ファイルが見つかりません: {dump_path}")
            raise
        except Exception as e:
            logger.error(f"ファイル解析に失敗: {e}")
            raise
    
    def _parse_values(self, values_str: str) -> List[str]:
        """VALUES部分の値を解析"""
        # 簡単な値の分割（SQLクオートとエスケープを考慮）
        values = []
        current_value = ""
        in_quote = False
        quote_char = None
        i = 0
        
        while i < len(values_str):
            char = values_str[i]
            
            if not in_quote:
                if char in ('"', "'"):
                    in_quote = True
                    quote_char = char
                elif char == ',':
                    values.append(current_value.strip())
                    current_value = ""
                    i += 1
                    continue
                else:
                    current_value += char
            else:
                if char == quote_char:
                    # エスケープされたクオートかチェック
                    if i + 1 < len(values_str) and values_str[i + 1] == quote_char:
                        current_value += char
                        i += 1  # 次の文字もスキップ
                    else:
                        in_quote = False
                        quote_char = None
                else:
                    current_value += char
            
            i += 1
        
        # 最後の値を追加
        if current_value.strip():
            values.append(current_value.strip())
        
        # クオートを削除
        cleaned_values = []
        for value in values:
            if value.startswith('"') and value.endswith('"'):
                cleaned_values.append(value[1:-1])
            elif value.startswith("'") and value.endswith("'"):
                cleaned_values.append(value[1:-1])
            else:
                cleaned_values.append(value)
        
        return cleaned_values
    
    def _convert_price(self, price_str: str) -> int:
        """価格文字列を整数に変換"""
        try:
            # 数字以外を除去
            price_num = re.sub(r'[^\d]', '', price_str)
            return int(price_num) if price_num else 0
        except (ValueError, TypeError):
            return 0
    
    def migrate_data(self, items: List[Tuple]) -> None:
        """データをPostgreSQLに移行"""
        try:
            with self.connection.cursor() as cursor:
                # 既存データをクリア（オプション）
                cursor.execute("TRUNCATE TABLE items")
                
                # バッチインサート
                execute_values(
                    cursor,
                    """
                    INSERT INTO items (item_code, title, price, status, updated_at)
                    VALUES %s
                    ON CONFLICT (item_code) DO UPDATE SET
                        title = EXCLUDED.title,
                        price = EXCLUDED.price,
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at
                    """,
                    items,
                    template=None,
                    page_size=100
                )
                
                self.connection.commit()
                logger.info(f"{len(items)}個のアイテムを移行しました")
                
        except psycopg2.Error as e:
            logger.error(f"データ移行に失敗: {e}")
            self.connection.rollback()
            raise
    
    def run_migration(self, sqlite_dump_path: str) -> None:
        """マイグレーション実行"""
        logger.info("マイグレーション開始")
        
        # テーブル準備
        self._setup_table()
        
        # SQLite dump 解析
        items = self._parse_sqlite_dump(sqlite_dump_path)
        
        # データ移行
        if items:
            self.migrate_data(items)
            logger.info("マイグレーション完了")
        else:
            logger.warning("移行するデータが見つかりませんでした")
    
    def close(self) -> None:
        """接続を閉じる"""
        if self.connection:
            self.connection.close()


def main():
    parser = argparse.ArgumentParser(description='SQLite dump から PostgreSQL への移行')
    parser.add_argument('--sqlite-dump', required=True, help='SQLite dump ファイルのパス')
    
    args = parser.parse_args()
    
    migrator = SQLiteToPGMigrator()
    try:
        migrator.run_migration(args.sqlite_dump)
    finally:
        migrator.close()


if __name__ == '__main__':
    main()