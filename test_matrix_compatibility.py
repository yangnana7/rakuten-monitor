#!/usr/bin/env python3
"""
マルチ Python バージョン・データベース対応のテスト
"""

import pytest
import sys
import os

class TestMatrixCompatibility:
    """マトリックステスト - Python バージョンとデータベース互換性"""
    
    def test_python_version_info(self):
        """Python バージョン情報のテスト"""
        print(f"Python version: {sys.version}")
        print(f"Version info: {sys.version_info}")
        
        # サポートされているPythonバージョンかチェック
        assert sys.version_info >= (3, 10), "Python 3.10以上が必要"
        assert sys.version_info < (4, 0), "Python 4.0未満である必要がある"
    
    def test_database_type_detection(self):
        """データベースタイプ検出のテスト"""
        test_db_type = os.environ.get('TEST_DATABASE_TYPE', 'sqlite')
        
        print(f"Test database type: {test_db_type}")
        
        if test_db_type == 'postgresql':
            # PostgreSQL固有のテスト
            self._test_postgresql_features()
        else:
            # SQLite固有のテスト
            self._test_sqlite_features()
    
    def _test_postgresql_features(self):
        """PostgreSQL固有機能のテスト"""
        try:
            import psycopg2
            print(f"psycopg2 version: {psycopg2.__version__}")
        except ImportError:
            pytest.skip("psycopg2 not available")
        
        # PostgreSQL用のupsert構文テスト
        from sqlalchemy.dialects.postgresql import insert
        assert insert is not None
        
        print("PostgreSQL features test passed")
    
    def _test_sqlite_features(self):
        """SQLite固有機能のテスト"""
        import sqlite3
        print(f"SQLite version: {sqlite3.sqlite_version}")
        
        # SQLite用のINSERT OR REPLACE構文テスト
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        cursor.execute("INSERT OR REPLACE INTO test (id, value) VALUES (1, 'test')")
        conn.close()
        
        print("SQLite features test passed")
    
    def test_import_compatibility(self):
        """重要なモジュールのインポート互換性テスト"""
        modules_to_test = [
            'requests',
            'beautifulsoup4',
            'sqlalchemy', 
            'alembic',
            'prometheus_client',
            'cloudscraper'
        ]
        
        failed_imports = []
        
        for module_name in modules_to_test:
            try:
                if module_name == 'beautifulsoup4':
                    import bs4
                    print(f"✓ {module_name}: {bs4.__version__}")
                else:
                    module = __import__(module_name)
                    version = getattr(module, '__version__', 'unknown')
                    print(f"✓ {module_name}: {version}")
            except ImportError as e:
                failed_imports.append((module_name, str(e)))
                print(f"✗ {module_name}: {e}")
        
        assert not failed_imports, f"Failed to import: {failed_imports}"
    
    def test_playwright_availability(self):
        """Playwright の可用性テスト"""
        try:
            import importlib.util
            spec = importlib.util.find_spec("playwright.async_api")
            if spec is not None:
                print("✓ Playwright available")
            else:
                print("⚠ Playwright not available (optional)")
        except ImportError:
            print("⚠ Playwright not available (optional)")
            # PlaywrightはオプショナルなのでテストはFAILしない
    
    def test_cloudflare_bypass_methods(self):
        """Cloudflare バイパス機能のテスト"""
        from fetch_items import fetch_with_cloudscraper, PLAYWRIGHT_AVAILABLE
        
        # cloudscraper の動作確認
        assert fetch_with_cloudscraper is not None
        
        # Playwright の可用性確認
        print(f"Playwright available: {PLAYWRIGHT_AVAILABLE}")
    
    def test_metrics_functionality(self):
        """メトリクス機能のテスト"""
        from metrics import (
            items_fetched_total, 
            run_duration_seconds,
            fetch_duration_seconds,
            upsert_duration_seconds
        )
        
        # メトリクスオブジェクトが正しく作成されているか確認
        assert items_fetched_total is not None
        assert run_duration_seconds is not None
        assert fetch_duration_seconds is not None
        assert upsert_duration_seconds is not None
        
        print("All metrics objects created successfully")
    
    def test_alembic_configuration(self):
        """Alembic設定のテスト"""
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        
        # SQLite用設定
        sqlite_config = Config('alembic.ini')
        sqlite_script_dir = ScriptDirectory.from_config(sqlite_config)
        sqlite_revisions = list(sqlite_script_dir.walk_revisions())
        
        print(f"SQLite revisions count: {len(sqlite_revisions)}")
        assert len(sqlite_revisions) >= 3
        
        # PostgreSQL用設定（ファイルが存在する場合）
        if os.path.exists('alembic.postgresql.ini'):
            pg_config = Config('alembic.postgresql.ini')
            pg_script_dir = ScriptDirectory.from_config(pg_config)
            pg_revisions = list(pg_script_dir.walk_revisions())
            
            print(f"PostgreSQL revisions count: {len(pg_revisions)}")
            assert len(pg_revisions) == len(sqlite_revisions)
    
    def test_environment_variables(self):
        """重要な環境変数のテスト"""
        important_vars = [
            'DATABASE_URL',
            'TEST_DATABASE_TYPE',
        ]
        
        for var in important_vars:
            value = os.environ.get(var)
            print(f"{var}: {value}")
        
        # DATABASE_URLが設定されていることを確認
        assert 'DATABASE_URL' in os.environ, "DATABASE_URL環境変数が必要"
    
    @pytest.mark.skipif(
        os.environ.get('TEST_DATABASE_TYPE') != 'postgresql',
        reason="PostgreSQL specific test"
    )
    def test_postgresql_specific_features(self):
        """PostgreSQL固有機能の詳細テスト"""
        from sqlalchemy import create_engine, text
        
        db_url = os.environ.get('DATABASE_URL')
        assert 'postgresql' in db_url
        
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # PostgreSQLバージョン確認
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"PostgreSQL version: {version}")
            
            # TimescaleDB拡張の確認（もしあれば）
            result = conn.execute(text("""
                SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')
            """))
            has_timescaledb = result.fetchone()[0]
            print(f"TimescaleDB available: {has_timescaledb}")
    
    @pytest.mark.skipif(
        os.environ.get('TEST_DATABASE_TYPE') != 'sqlite',
        reason="SQLite specific test"
    )
    def test_sqlite_specific_features(self):
        """SQLite固有機能の詳細テスト"""
        from sqlalchemy import create_engine, text
        
        db_url = os.environ.get('DATABASE_URL')
        assert 'sqlite' in db_url
        
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # SQLiteバージョン確認
            result = conn.execute(text("SELECT sqlite_version()"))
            version = result.fetchone()[0]
            print(f"SQLite version: {version}")
            
            # WALモード確認
            result = conn.execute(text("PRAGMA journal_mode"))
            journal_mode = result.fetchone()[0]
            print(f"Journal mode: {journal_mode}")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])