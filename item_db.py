"""SQLiteベースの商品データ管理"""
import sqlite3
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from .exceptions import DatabaseConnectionError


logger = logging.getLogger(__name__)


class ItemDatabase:
    """商品情報を管理するSQLiteデータベース"""
    
    def __init__(self, db_path: str = "rakuten_items.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self) -> None:
        """データベースの初期化とテーブル作成"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
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
                conn.commit()
                logger.info(f"Database initialized: {self.db_path}")
        except sqlite3.Error as e:
            raise DatabaseConnectionError(f"データベース初期化に失敗: {e}")
    
    def get_items_by_url(self, url: str) -> List[Dict[str, Any]]:
        """指定URLの全商品を取得"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM items WHERE url = ? ORDER BY last_updated DESC",
                    (url,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise DatabaseConnectionError(f"商品データ取得に失敗: {e}")
    
    def get_item(self, url: str, product_id: str) -> Optional[Dict[str, Any]]:
        """特定の商品を取得"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM items WHERE url = ? AND product_id = ?",
                    (url, product_id)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            raise DatabaseConnectionError(f"商品データ取得に失敗: {e}")
    
    def upsert_item(self, url: str, product_id: str, name: str, price: str, status: str) -> Dict[str, str]:
        """商品を挿入または更新し、変更状態を返す"""
        try:
            existing_item = self.get_item(url, product_id)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                if existing_item:
                    # 既存商品の更新
                    cursor.execute("""
                        UPDATE items 
                        SET name = ?, price = ?, status = ?, last_updated = ?
                        WHERE url = ? AND product_id = ?
                    """, (name, price, status, now, url, product_id))
                    
                    # 在庫状態の変化を判定
                    old_status = existing_item['status']
                    if old_status == '売り切れ' and status == '在庫あり':
                        change_type = 'restock'
                    elif old_status != status:
                        change_type = 'status_change'
                    else:
                        change_type = 'no_change'
                else:
                    # 新商品の挿入
                    cursor.execute("""
                        INSERT INTO items (url, product_id, name, price, status, first_seen, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (url, product_id, name, price, status, now, now))
                    change_type = 'new_item' if status == '在庫あり' else 'new_item_out_of_stock'
                
                conn.commit()
                
                return {
                    'change_type': change_type,
                    'name': name,
                    'price': price,
                    'status': status,
                    'url': url,
                    'product_id': product_id
                }
                
        except sqlite3.Error as e:
            raise DatabaseConnectionError(f"商品データ更新に失敗: {e}")
    
    def get_all_items(self) -> List[Dict[str, Any]]:
        """全商品を取得"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM items ORDER BY last_updated DESC")
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise DatabaseConnectionError(f"全商品データ取得に失敗: {e}")
    
    def cleanup_old_items(self, days: int = 30) -> int:
        """古い商品データを削除"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM items 
                    WHERE last_updated < datetime('now', '-{} days')
                """.format(days))
                deleted_count = cursor.rowcount
                conn.commit()
                logger.info(f"Cleaned up {deleted_count} old items")
                return deleted_count
        except sqlite3.Error as e:
            raise DatabaseConnectionError(f"古いデータの削除に失敗: {e}")


class LegacyJSONDatabase:
    """database.jsonとの互換性維持用クラス"""
    
    def __init__(self, json_path: str = "database.json"):
        self.json_path = json_path
    
    def migrate_to_sqlite(self, sqlite_db: ItemDatabase) -> int:
        """JSONデータをSQLiteに移行"""
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            migrated_count = 0
            for url, items in data.items():
                for item in items:
                    sqlite_db.upsert_item(
                        url=url,
                        product_id=item.get('id', f"legacy_{migrated_count}"),
                        name=item.get('name', 'Unknown'),
                        price=item.get('price', '不明'),
                        status=item.get('status', '不明')
                    )
                    migrated_count += 1
            
            logger.info(f"Migrated {migrated_count} items from JSON to SQLite")
            return migrated_count
            
        except FileNotFoundError:
            logger.info("No legacy JSON database found")
            return 0
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to migrate legacy data: {e}")
            return 0