"""アイテムデータベース操作モジュール - Phase1."""

import sqlite3
from typing import Dict, List, Optional


class ItemDB:
    """商品データベース操作クラス."""

    def __init__(self, db_path: str):
        """
        データベースを初期化する。

        Args:
            db_path (str): SQLiteデータベースファイルのパス
        """
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """データベーステーブルを初期化する."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    item_code TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            conn.commit()

    def save_item(self, item_data: Dict[str, str]) -> bool:
        """
        商品データをデータベースに保存する。

        Args:
            item_data (Dict[str, str]): 商品データ辞書
                - item_code: 商品コード
                - title: 商品タイトル
                - status: 商品ステータス

        Returns:
            bool: 保存成功時True、重複時False
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO items (item_code, title, status)
                    VALUES (?, ?, ?)
                """,
                    (item_data["item_code"], item_data["title"], item_data["status"]),
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            # Primary key constraint violation (duplicate item_code)
            return False

    def item_exists(self, item_code: str) -> bool:
        """
        指定された商品コードが存在するかチェックする。

        Args:
            item_code (str): 商品コード

        Returns:
            bool: 存在する場合True
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM items WHERE item_code = ?", (item_code,))
            return cursor.fetchone() is not None

    def get_item(self, item_code: str) -> Optional[Dict[str, str]]:
        """
        指定された商品コードの商品データを取得する。

        Args:
            item_code (str): 商品コード

        Returns:
            Optional[Dict[str, str]]: 商品データ辞書、存在しない場合None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT item_code, title, status
                FROM items 
                WHERE item_code = ?
            """,
                (item_code,),
            )
            row = cursor.fetchone()

            if row:
                return {
                    "item_code": row["item_code"],
                    "title": row["title"],
                    "status": row["status"],
                }
            return None

    def update_item_status(self, item_code: str, new_status: str) -> bool:
        """
        商品のステータスを更新する。

        Args:
            item_code (str): 商品コード
            new_status (str): 新しいステータス

        Returns:
            bool: 更新成功時True
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE items 
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE item_code = ?
                """,
                    (new_status, item_code),
                )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error:
            return False

    def update_item(self, item_code: str, data_dict: Dict[str, str]) -> bool:
        """
        商品データを更新する（指示書期待インターフェース対応）。

        Args:
            item_code (str): 商品コード
            data_dict (Dict[str, str]): 更新データ辞書

        Returns:
            bool: 更新成功時True
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 更新可能なフィールドのリスト
                update_fields = []
                update_values = []

                if "title" in data_dict:
                    update_fields.append("title = ?")
                    update_values.append(data_dict["title"])

                if "status" in data_dict:
                    update_fields.append("status = ?")
                    update_values.append(data_dict["status"])

                if not update_fields:
                    return False

                # updated_atフィールドも更新
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                update_values.append(item_code)

                query = f"""
                    UPDATE items 
                    SET {', '.join(update_fields)}
                    WHERE item_code = ?
                """

                cursor.execute(query, update_values)
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error:
            return False

    def get_all_items(self) -> List[Dict[str, str]]:
        """
        すべての商品データを取得する。

        Returns:
            List[Dict[str, str]]: 商品データのリスト
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT item_code, title, status
                FROM items 
                ORDER BY created_at DESC
            """
            )
            rows = cursor.fetchall()

            return [
                {
                    "item_code": row["item_code"],
                    "title": row["title"],
                    "status": row["status"],
                }
                for row in rows
            ]
