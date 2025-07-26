#!/usr/bin/env python3
"""
SQLiteからPostgreSQLへのデータ移行スクリプト
"""

import os
import sys
import time
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# プロジェクトのモジュールをインポート
from models import Base, Item, Change, Run

load_dotenv()

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseMigrator:
    """データベース移行クラス"""
    
    def __init__(self, sqlite_url: str, postgres_url: str):
        self.sqlite_url = sqlite_url
        self.postgres_url = postgres_url
        
        # SQLiteエンジン
        self.sqlite_engine = create_engine(sqlite_url)
        self.SqliteSession = sessionmaker(bind=self.sqlite_engine)
        
        # PostgreSQLエンジン
        self.postgres_engine = create_engine(postgres_url)
        self.PostgresSession = sessionmaker(bind=self.postgres_engine)
    
    def verify_connections(self) -> bool:
        """データベース接続の確認"""
        try:
            # SQLite接続確認
            with self.sqlite_engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                assert result.fetchone()[0] == 1
            logger.info("SQLite connection verified")
            
            # PostgreSQL接続確認
            with self.postgres_engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                assert result.fetchone()[0] == 1
            logger.info("PostgreSQL connection verified")
            
            return True
            
        except Exception as e:
            logger.error(f"Connection verification failed: {e}")
            return False
    
    def create_postgres_schema(self):
        """PostgreSQLスキーマ作成"""
        try:
            logger.info("Creating PostgreSQL schema...")
            Base.metadata.create_all(self.postgres_engine)
            logger.info("PostgreSQL schema created successfully")
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL schema: {e}")
            raise
    
    def migrate_items(self) -> int:
        """商品データの移行"""
        logger.info("Migrating items table...")
        
        sqlite_session = self.SqliteSession()
        postgres_session = self.PostgresSession()
        
        try:
            # SQLiteからデータ取得
            sqlite_items = sqlite_session.query(Item).all()
            migrated_count = 0
            
            for sqlite_item in sqlite_items:
                # PostgreSQLに挿入
                postgres_item = Item(
                    code=sqlite_item.code,
                    title=sqlite_item.title,
                    price=sqlite_item.price,
                    in_stock=sqlite_item.in_stock,
                    first_seen=sqlite_item.first_seen,
                    last_seen=sqlite_item.last_seen
                )
                postgres_session.merge(postgres_item)
                migrated_count += 1
                
                if migrated_count % 100 == 0:
                    postgres_session.commit()
                    logger.info(f"Migrated {migrated_count} items...")
            
            postgres_session.commit()
            logger.info(f"Items migration completed: {migrated_count} records")
            return migrated_count
            
        except Exception as e:
            postgres_session.rollback()
            logger.error(f"Failed to migrate items: {e}")
            raise
        finally:
            sqlite_session.close()
            postgres_session.close()
    
    def migrate_changes(self) -> int:
        """変更履歴データの移行"""
        logger.info("Migrating changes table...")
        
        sqlite_session = self.SqliteSession()
        postgres_session = self.PostgresSession()
        
        try:
            # SQLiteからデータ取得
            sqlite_changes = sqlite_session.query(Change).all()
            migrated_count = 0
            
            for sqlite_change in sqlite_changes:
                # PostgreSQLに挿入
                postgres_change = Change(
                    id=sqlite_change.id,
                    code=sqlite_change.code,
                    type=sqlite_change.type,
                    payload=sqlite_change.payload,
                    occurred_at=sqlite_change.occurred_at
                )
                postgres_session.merge(postgres_change)
                migrated_count += 1
                
                if migrated_count % 500 == 0:
                    postgres_session.commit()
                    logger.info(f"Migrated {migrated_count} changes...")
            
            postgres_session.commit()
            logger.info(f"Changes migration completed: {migrated_count} records")
            return migrated_count
            
        except Exception as e:
            postgres_session.rollback()
            logger.error(f"Failed to migrate changes: {e}")
            raise
        finally:
            sqlite_session.close()
            postgres_session.close()
    
    def migrate_runs(self) -> int:
        """実行履歴データの移行"""
        logger.info("Migrating runs table...")
        
        sqlite_session = self.SqliteSession()
        postgres_session = self.PostgresSession()
        
        try:
            # SQLiteからデータ取得
            sqlite_runs = sqlite_session.query(Run).all()
            migrated_count = 0
            
            for sqlite_run in sqlite_runs:
                # PostgreSQLに挿入
                postgres_run = Run(
                    id=sqlite_run.id,
                    fetched_at=sqlite_run.fetched_at,
                    snapshot=sqlite_run.snapshot
                )
                postgres_session.merge(postgres_run)
                migrated_count += 1
                
                if migrated_count % 100 == 0:
                    postgres_session.commit()
                    logger.info(f"Migrated {migrated_count} runs...")
            
            postgres_session.commit()
            logger.info(f"Runs migration completed: {migrated_count} records")
            return migrated_count
            
        except Exception as e:
            postgres_session.rollback()
            logger.error(f"Failed to migrate runs: {e}")
            raise
        finally:
            sqlite_session.close()
            postgres_session.close()
    
    def setup_timescale_hypertables(self):
        """TimescaleDB hypertableの設定"""
        try:
            with self.postgres_engine.connect() as conn:
                # TimescaleDBが利用可能か確認
                result = conn.execute(text("""
                    SELECT EXISTS(
                        SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
                    )
                """))
                
                if not result.fetchone()[0]:
                    logger.warning("TimescaleDB extension not found, skipping hypertable setup")
                    return
                
                # runsテーブルをhypertableに変換
                conn.execute(text("""
                    SELECT create_hypertable('runs', 'fetched_at', 
                                            if_not_exists => TRUE,
                                            migrate_data => TRUE)
                """))
                
                # データ保持ポリシーの設定（90日間）
                conn.execute(text("""
                    SELECT add_retention_policy('runs', INTERVAL '90 days', 
                                              if_not_exists => TRUE)
                """))
                
                conn.commit()
                logger.info("TimescaleDB hypertable setup completed")
                
        except Exception as e:
            logger.error(f"Failed to setup TimescaleDB hypertables: {e}")
            # TimescaleDB固有の機能なので、エラーでも継続
    
    def verify_migration(self) -> bool:
        """移行結果の検証"""
        logger.info("Verifying migration...")
        
        sqlite_session = self.SqliteSession()
        postgres_session = self.PostgresSession()
        
        try:
            # レコード数の比較
            sqlite_items_count = sqlite_session.query(Item).count()
            postgres_items_count = postgres_session.query(Item).count()
            
            sqlite_changes_count = sqlite_session.query(Change).count()
            postgres_changes_count = postgres_session.query(Change).count()
            
            sqlite_runs_count = sqlite_session.query(Run).count()
            postgres_runs_count = postgres_session.query(Run).count()
            
            logger.info(f"Items: SQLite={sqlite_items_count}, PostgreSQL={postgres_items_count}")
            logger.info(f"Changes: SQLite={sqlite_changes_count}, PostgreSQL={postgres_changes_count}")
            logger.info(f"Runs: SQLite={sqlite_runs_count}, PostgreSQL={postgres_runs_count}")
            
            # レコード数が一致するか確認
            if (sqlite_items_count == postgres_items_count and
                sqlite_changes_count == postgres_changes_count and
                sqlite_runs_count == postgres_runs_count):
                logger.info("Migration verification passed")
                return True
            else:
                logger.error("Migration verification failed: record counts don't match")
                return False
                
        except Exception as e:
            logger.error(f"Failed to verify migration: {e}")
            return False
        finally:
            sqlite_session.close()
            postgres_session.close()
    
    def run_migration(self) -> bool:
        """完全な移行プロセスの実行"""
        start_time = time.time()
        logger.info("Starting database migration...")
        
        try:
            # 1. 接続確認
            if not self.verify_connections():
                return False
            
            # 2. PostgreSQLスキーマ作成
            self.create_postgres_schema()
            
            # 3. データ移行
            items_count = self.migrate_items()
            changes_count = self.migrate_changes()
            runs_count = self.migrate_runs()
            
            # 4. TimescaleDB設定
            self.setup_timescale_hypertables()
            
            # 5. 移行結果検証
            if not self.verify_migration():
                return False
            
            duration = time.time() - start_time
            logger.info(f"Migration completed successfully in {duration:.2f}s")
            logger.info(f"Migrated: {items_count} items, {changes_count} changes, {runs_count} runs")
            
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

def main():
    """メイン実行関数"""
    # 環境変数から設定取得
    sqlite_url = os.getenv('SQLITE_DATABASE_URL', 'sqlite:///rakuten_monitor.db')
    postgres_url = os.getenv('POSTGRES_DATABASE_URL', 
                           'postgresql://rakuten_user:rakuten_pass@localhost:5432/rakuten_monitor')
    
    print(f"Migration from: {sqlite_url}")
    print(f"Migration to: {postgres_url}")
    
    # 確認プロンプト
    if len(sys.argv) < 2 or sys.argv[1] != '--confirm':
        print("\nThis will migrate data from SQLite to PostgreSQL.")
        print("Make sure PostgreSQL is running and accessible.")
        print("Add --confirm flag to proceed.")
        return 1
    
    # 移行実行
    migrator = DatabaseMigrator(sqlite_url, postgres_url)
    
    if migrator.run_migration():
        print("\n✅ Migration completed successfully!")
        print(f"You can now update DATABASE_URL to: {postgres_url}")
        return 0
    else:
        print("\n❌ Migration failed!")
        return 1

if __name__ == "__main__":
    exit(main())