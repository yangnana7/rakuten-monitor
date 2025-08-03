"""PostgreSQLベースの商品データ管理"""
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
try:
    from .exceptions import DatabaseConnectionError
except ImportError:
    from exceptions import DatabaseConnectionError


logger = logging.getLogger(__name__)


class ItemDB:
    """商品情報を管理するPostgreSQLデータベース"""
    
    def __init__(self):
        self.connection = None
        self._connect()
        self._init_database()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.close()
    
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
            raise DatabaseConnectionError(f"PostgreSQL接続に失敗: {e}")
    
    def _init_database(self) -> None:
        """データベースの初期化とテーブル作成"""
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
                logger.info("Database initialized")
        except psycopg2.Error as e:
            raise DatabaseConnectionError(f"データベース初期化に失敗: {e}")
    
    def get_item(self, item_code: str) -> Optional[Dict[str, Any]]:
        """特定の商品を取得"""
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM items WHERE item_code = %s",
                    (item_code,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except psycopg2.Error as e:
            raise DatabaseConnectionError(f"商品データ取得に失敗: {e}")
    
    def save_item(self, item_dict: Dict[str, Any]) -> None:
        """商品をアップサート"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO items (item_code, title, price, status, updated_at)
                    VALUES (%(item_code)s, %(title)s, %(price)s, %(status)s, %s)
                    ON CONFLICT (item_code) DO UPDATE SET
                        title = EXCLUDED.title,
                        price = EXCLUDED.price,
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at
                """, (*item_dict.values(), datetime.now()))
                self.connection.commit()
        except psycopg2.Error as e:
            raise DatabaseConnectionError(f"商品データ保存に失敗: {e}")
    
    def update_status(self, item_code: str, status: str) -> None:
        """商品ステータスを更新"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE items 
                    SET status = %s, updated_at = %s
                    WHERE item_code = %s
                """, (status, datetime.now(), item_code))
                self.connection.commit()
        except psycopg2.Error as e:
            raise DatabaseConnectionError(f"ステータス更新に失敗: {e}")
    
    def get_all_items(self) -> List[Dict[str, Any]]:
        """全商品を取得"""
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM items ORDER BY updated_at DESC")
                return [dict(row) for row in cursor.fetchall()]
        except psycopg2.Error as e:
            raise DatabaseConnectionError(f"全商品データ取得に失敗: {e}")
    
    def cleanup_old_items(self, days: int = 30) -> int:
        """古い商品データを削除"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM items 
                    WHERE updated_at < NOW() - INTERVAL '%s days'
                """, (days,))
                deleted_count = cursor.rowcount
                self.connection.commit()
                logger.info(f"Cleaned up {deleted_count} old items")
                return deleted_count
        except psycopg2.Error as e:
            raise DatabaseConnectionError(f"古いデータの削除に失敗: {e}")


# 旧ItemDatabaseクラスとの互換性のためのエイリアス
ItemDatabase = ItemDB