"""楽天監視システムのデータモデル"""

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

try:
    from .exceptions import DatabaseConnectionError
    from .html_parser import Product
except ImportError:
    from exceptions import DatabaseConnectionError
    from html_parser import Product

logger = logging.getLogger(__name__)


@dataclass
class ProductState:
    """商品の状態管理用データクラス"""
    id: str                    # 商品ID
    url: str                   # 商品URL
    name: str                  # 商品名
    price: int                 # 現在の価格
    in_stock: bool            # 現在の在庫状況
    last_seen_at: datetime    # 最後に確認された日時
    first_seen_at: datetime   # 初回発見日時
    stock_change_count: int = 0  # 在庫状況変更回数
    price_change_count: int = 0  # 価格変更回数
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        data = asdict(self)
        # datetimeを文字列に変換
        data['last_seen_at'] = self.last_seen_at.isoformat()
        data['first_seen_at'] = self.first_seen_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProductState':
        """辞書から復元"""
        # 文字列をdatetimeに変換
        data['last_seen_at'] = datetime.fromisoformat(data['last_seen_at'])
        data['first_seen_at'] = datetime.fromisoformat(data['first_seen_at'])
        return cls(**data)
    
    @classmethod
    def from_product(cls, product: Product) -> 'ProductState':
        """Productオブジェクトから作成"""
        now = datetime.now()
        return cls(
            id=product.id,
            url=product.url,
            name=product.name,
            price=product.price,
            in_stock=product.in_stock,
            last_seen_at=now,
            first_seen_at=now,
            stock_change_count=0,
            price_change_count=0
        )
    
    def update_from_product(self, product: Product) -> bool:
        """Productオブジェクトから状態を更新
        
        Returns:
            bool: 変更があった場合True
        """
        changed = False
        
        # 在庫状況の変更をチェック
        if self.in_stock != product.in_stock:
            self.stock_change_count += 1
            self.in_stock = product.in_stock
            changed = True
        
        # 価格変更をチェック
        if self.price != product.price:
            self.price_change_count += 1
            self.price = product.price
            changed = True
        
        # 商品名の更新（通常は変わらないが念のため）
        if self.name != product.name:
            self.name = product.name
            changed = True
        
        # URLの更新
        if self.url != product.url:
            self.url = product.url
            changed = True
        
        # 最終確認時刻は常に更新
        self.last_seen_at = datetime.now()
        
        return changed


@dataclass
class DiffResult:
    """監視結果の差分データ"""
    new_items: List[Product]      # 新規商品
    restocked: List[Product]      # 再販商品
    out_of_stock: List[Product]   # 売り切れ商品
    price_changed: List[tuple]    # 価格変更商品 (old_product, new_product)
    updated_items: List[Product]  # その他更新された商品


class ProductStateManager:
    """商品状態を管理するクラス"""
    
    def __init__(self, storage_type: str = "sqlite", storage_path: str = "product_states.db"):
        """
        Args:
            storage_type: 'sqlite' または 'json'
            storage_path: ストレージファイルのパス
        """
        self.storage_type = storage_type.lower()
        self.storage_path = Path(storage_path) if storage_path != ":memory:" else storage_path
        
        # データベース接続リトライ設定（指数バックオフ: 1秒→2秒→4秒）
        self.max_db_retries = 3
        self.db_retry_delays = [1, 2, 4]
        
        # In-memory databases need persistent connection
        self._persistent_conn = None
        
        if self.storage_type == "sqlite":
            self._init_sqlite_with_retry()
        elif self.storage_type == "json":
            self._init_json()
        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")
    
    def _retry_db_operation(self, operation_func, *args, **kwargs):
        """データベース操作をリトライ機能付きで実行"""
        last_exception = None
        
        for attempt in range(self.max_db_retries):
            try:
                return operation_func(*args, **kwargs)
            except sqlite3.Error as e:
                last_exception = DatabaseConnectionError(f"Database operation failed: {e}")
                if attempt < self.max_db_retries - 1:
                    delay = self.db_retry_delays[attempt]
                    logger.warning(f"Database operation failed, retrying in {delay}s (attempt {attempt + 1}/{self.max_db_retries}): {e}")
                    time.sleep(delay)
                else:
                    logger.error(f"Database operation failed after {self.max_db_retries} attempts: {e}")
        
        raise last_exception
    
    def _init_sqlite_with_retry(self):
        """リトライ機能付きでSQLiteデータベースを初期化"""
        def init_operation():
            # For in-memory databases, keep persistent connection
            if self.storage_path == ":memory:":
                if not self._persistent_conn:
                    self._persistent_conn = sqlite3.connect(self.storage_path)
                conn = self._persistent_conn
            else:
                conn = sqlite3.connect(self.storage_path)
            
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS product_states (
                        id TEXT PRIMARY KEY,
                        url TEXT NOT NULL,
                        name TEXT NOT NULL,
                        price INTEGER NOT NULL,
                        in_stock BOOLEAN NOT NULL,
                        last_seen_at TEXT NOT NULL,
                        first_seen_at TEXT NOT NULL,
                        stock_change_count INTEGER DEFAULT 0,
                        price_change_count INTEGER DEFAULT 0
                    )
                """)
                conn.commit()
                logger.info(f"SQLite database initialized: {self.storage_path}")
            finally:
                if self.storage_path != ":memory:":
                    conn.close()
        
        self._retry_db_operation(init_operation)
    
    
    def _init_json(self):
        """JSONストレージを初期化"""
        if not self.storage_path.exists():
            self.storage_path.write_text("{}")
            logger.info(f"JSON storage initialized: {self.storage_path}")
    
    def get_product_state(self, product_id: str) -> Optional[ProductState]:
        """商品状態を取得"""
        if self.storage_type == "sqlite":
            return self._get_product_state_sqlite(product_id)
        else:
            return self._get_product_state_json(product_id)
    
    def save_product_state(self, state: ProductState):
        """商品状態を保存"""
        if self.storage_type == "sqlite":
            self._save_product_state_sqlite(state)
        else:
            self._save_product_state_json(state)
    
    def get_all_product_states(self) -> List[ProductState]:
        """すべての商品状態を取得"""
        if self.storage_type == "sqlite":
            return self._get_all_product_states_sqlite()
        else:
            return self._get_all_product_states_json()
    
    def delete_product_state(self, product_id: str):
        """商品状態を削除"""
        if self.storage_type == "sqlite":
            self._delete_product_state_sqlite(product_id)
        else:
            self._delete_product_state_json(product_id)
    
    # SQLite実装（リトライ機能付き）
    def _get_product_state_sqlite(self, product_id: str) -> Optional[ProductState]:
        def get_operation():
            # For in-memory databases, use persistent connection
            if self.storage_path == ":memory:":
                conn = self._persistent_conn
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM product_states WHERE id = ?", (product_id,)
                )
                row = cursor.fetchone()
                if row:
                    data = dict(row)
                    data['in_stock'] = bool(data['in_stock'])
                    return ProductState.from_dict(data)
                return None
            else:
                with sqlite3.connect(self.storage_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute(
                        "SELECT * FROM product_states WHERE id = ?", (product_id,)
                    )
                    row = cursor.fetchone()
                    if row:
                        data = dict(row)
                        data['in_stock'] = bool(data['in_stock'])
                        return ProductState.from_dict(data)
                return None
        
        return self._retry_db_operation(get_operation)
    
    def _save_product_state_sqlite(self, state: ProductState):
        def save_operation():
            # For in-memory databases, use persistent connection
            if self.storage_path == ":memory:":
                conn = self._persistent_conn
                conn.execute("""
                    INSERT OR REPLACE INTO product_states 
                    (id, url, name, price, in_stock, last_seen_at, first_seen_at, 
                     stock_change_count, price_change_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    state.id, state.url, state.name, state.price, 
                    state.in_stock, state.last_seen_at.isoformat(), 
                    state.first_seen_at.isoformat(),
                    state.stock_change_count, state.price_change_count
                ))
                conn.commit()
            else:
                with sqlite3.connect(self.storage_path) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO product_states 
                        (id, url, name, price, in_stock, last_seen_at, first_seen_at, 
                         stock_change_count, price_change_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        state.id, state.url, state.name, state.price, 
                        state.in_stock, state.last_seen_at.isoformat(), 
                        state.first_seen_at.isoformat(),
                        state.stock_change_count, state.price_change_count
                    ))
                    conn.commit()
        
        self._retry_db_operation(save_operation)
    
    def _get_all_product_states_sqlite(self) -> List[ProductState]:
        try:
            # For in-memory databases, use persistent connection
            if self.storage_path == ":memory:":
                conn = self._persistent_conn
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM product_states")
                states = []
                for row in cursor:
                    data = dict(row)
                    data['in_stock'] = bool(data['in_stock'])
                    states.append(ProductState.from_dict(data))
                return states
            else:
                with sqlite3.connect(self.storage_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute("SELECT * FROM product_states")
                    states = []
                    for row in cursor:
                        data = dict(row)
                        data['in_stock'] = bool(data['in_stock'])
                        states.append(ProductState.from_dict(data))
                    return states
        except sqlite3.Error as e:
            raise DatabaseConnectionError(f"Failed to get all product states: {e}")
    
    def _delete_product_state_sqlite(self, product_id: str):
        try:
            # For in-memory databases, use persistent connection
            if self.storage_path == ":memory:":
                conn = self._persistent_conn
                conn.execute("DELETE FROM product_states WHERE id = ?", (product_id,))
                conn.commit()
            else:
                with sqlite3.connect(self.storage_path) as conn:
                    conn.execute("DELETE FROM product_states WHERE id = ?", (product_id,))
                    conn.commit()
        except sqlite3.Error as e:
            raise DatabaseConnectionError(f"Failed to delete product state: {e}")
    
    # JSON実装
    def _get_product_state_json(self, product_id: str) -> Optional[ProductState]:
        try:
            if not self.storage_path.exists():
                return None
            
            data = json.loads(self.storage_path.read_text())
            if product_id in data:
                return ProductState.from_dict(data[product_id])
            return None
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to get product state from JSON: {e}")
            return None
    
    def _save_product_state_json(self, state: ProductState):
        try:
            # 既存データを読み込み
            if self.storage_path.exists():
                data = json.loads(self.storage_path.read_text())
            else:
                data = {}
            
            # 状態を更新
            data[state.id] = state.to_dict()
            
            # ファイルに書き込み
            self.storage_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except (json.JSONDecodeError, OSError) as e:
            raise DatabaseConnectionError(f"Failed to save product state to JSON: {e}")
    
    def _get_all_product_states_json(self) -> List[ProductState]:
        try:
            if not self.storage_path.exists():
                return []
            
            data = json.loads(self.storage_path.read_text())
            states = []
            for product_data in data.values():
                states.append(ProductState.from_dict(product_data))
            return states
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to get all product states from JSON: {e}")
            return []
    
    def _delete_product_state_json(self, product_id: str):
        try:
            if not self.storage_path.exists():
                return
            
            data = json.loads(self.storage_path.read_text())
            if product_id in data:
                del data[product_id]
                self.storage_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to delete product state from JSON: {e}")


def detect_changes(current_products: List[Product], state_manager: ProductStateManager) -> DiffResult:
    """
    現在の商品リストと保存された状態を比較して変更を検出
    
    Args:
        current_products: 現在取得した商品リスト
        state_manager: 商品状態管理オブジェクト
        
    Returns:
        DiffResult: 検出された変更
    """
    new_items = []
    restocked = []
    out_of_stock = []
    price_changed = []
    updated_items = []
    
    # 現在の商品をIDでマップ
    current_by_id = {p.id: p for p in current_products}
    
    # 既存の状態を取得
    existing_states = {s.id: s for s in state_manager.get_all_product_states()}
    
    # 現在の商品をチェック
    for product in current_products:
        existing_state = existing_states.get(product.id)
        
        if existing_state is None:
            # 新規商品
            if product.in_stock:  # 在庫ありの新規商品のみ通知
                new_items.append(product)
            # 状態を保存
            new_state = ProductState.from_product(product)
            state_manager.save_product_state(new_state)
        else:
            # 既存商品の更新チェック
            old_price = existing_state.price
            old_stock = existing_state.in_stock
            
            # 状態を更新
            changed = existing_state.update_from_product(product)
            
            if changed:
                # 再販チェック（売り切れ → 在庫あり）
                if not old_stock and product.in_stock:
                    restocked.append(product)
                
                # 売り切れチェック（在庫あり → 売り切れ）
                elif old_stock and not product.in_stock:
                    out_of_stock.append(product)
                
                # 価格変更チェック
                if old_price != product.price and product.in_stock:
                    # 古い商品情報を作成
                    old_product = Product(
                        id=product.id,
                        name=existing_state.name,
                        price=old_price,
                        url=product.url,
                        in_stock=old_stock
                    )
                    price_changed.append((old_product, product))
                
                # その他の更新
                updated_items.append(product)
                
                # 状態を保存
                state_manager.save_product_state(existing_state)
    
    return DiffResult(
        new_items=new_items,
        restocked=restocked,
        out_of_stock=out_of_stock,
        price_changed=price_changed,
        updated_items=updated_items
    )


if __name__ == "__main__":
    # テスト用
    logging.basicConfig(level=logging.DEBUG)
    
    # SQLiteテスト
    manager = ProductStateManager("sqlite", "test_states.db")
    
    # テスト商品を作成
    test_product = Product(
        id="test123",
        name="テスト商品",
        price=1000,
        url="https://example.com/test",
        in_stock=True
    )
    
    # 状態を保存
    state = ProductState.from_product(test_product)
    manager.save_product_state(state)
    
    # 状態を取得
    retrieved_state = manager.get_product_state("test123")
    print(f"Retrieved state: {retrieved_state}")
    
    # 全状態を取得
    all_states = manager.get_all_product_states()
    print(f"All states: {len(all_states)} items")
    
    print("Test completed successfully!")