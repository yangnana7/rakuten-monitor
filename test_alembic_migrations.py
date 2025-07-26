#!/usr/bin/env python3
"""
Alembic マイグレーションのテスト
"""

import pytest
import tempfile
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

from models import ChangeType, Item, Change

class TestAlembicMigrations:
    """Alembic マイグレーションのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        self.test_db_url = f"sqlite:///{self.temp_db.name}"
        self.engine = create_engine(self.test_db_url)
        
        # Alembic設定
        self.alembic_cfg = Config()
        self.alembic_cfg.set_main_option("script_location", "alembic")
        self.alembic_cfg.set_main_option("sqlalchemy.url", self.test_db_url)
    
    def teardown_method(self):
        """テスト後処理"""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_migration_from_scratch(self):
        """ゼロからのマイグレーションテスト"""
        # 最新リビジョンまでマイグレーション実行
        command.upgrade(self.alembic_cfg, "head")
        
        # テーブルが作成されているか確認
        with self.engine.connect() as conn:
            # itemsテーブルの存在確認
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='items'"))
            assert result.fetchone() is not None
            
            # changesテーブルの存在確認
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='changes'"))
            assert result.fetchone() is not None
            
            # runsテーブルの存在確認
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'"))
            assert result.fetchone() is not None
    
    def test_revision_history(self):
        """リビジョン履歴の整合性テスト"""
        script_dir = ScriptDirectory.from_config(self.alembic_cfg)
        revisions = list(script_dir.walk_revisions())
        
        # リビジョンが存在することを確認
        assert len(revisions) >= 3
        
        # 各リビジョンが適切な構造を持つことを確認
        for revision in revisions:
            assert revision.revision is not None
            assert revision.doc is not None
    
    def test_no_empty_revisions(self):
        """空のリビジョンが存在しないことをテスト"""
        script_dir = ScriptDirectory.from_config(self.alembic_cfg)
        
        for revision in script_dir.walk_revisions():
            # リビジョンファイルを読み込み
            revision_file = revision.path
            with open(revision_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # upgrade関数内にpassのみが存在しないことを確認
            upgrade_section = content[content.find('def upgrade()'):content.find('def downgrade()')]
            
            # 単純なpassのみのupgrade関数でないことを確認
            # (ただし、PRICE_UPDATE revisionは例外として許可)
            if "db233a178353" not in revision_file:  # PRICE_UPDATE revision以外
                assert not (upgrade_section.count('pass') == 1 and upgrade_section.count('\n') <= 10)
    
    def test_price_update_enum_in_models(self):
        """PRICE_UPDATE enumがモデルに含まれていることをテスト"""
        # ChangeTypeにPRICE_UPDATEが含まれることを確認
        assert hasattr(ChangeType, 'PRICE_UPDATE')
        assert ChangeType.PRICE_UPDATE.value == 'PRICE_UPDATE'
        
        # 全ての期待される変更タイプが存在することを確認
        expected_types = {'NEW', 'RESTOCK', 'TITLE_UPDATE', 'PRICE_UPDATE', 'SOLDOUT'}
        actual_types = {ct.value for ct in ChangeType}
        assert expected_types == actual_types
    
    def test_migration_data_integrity(self):
        """マイグレーション後のデータ整合性テスト"""
        # マイグレーション実行
        command.upgrade(self.alembic_cfg, "head")
        
        # セッション作成
        Session = sessionmaker(bind=self.engine)
        session = Session()
        
        try:
            # テストデータの挿入
            test_item = Item(
                code='test-001',
                title='テスト商品',
                price=1000,
                in_stock=True
            )
            session.add(test_item)
            session.commit()
            
            # 変更イベントの挿入（全タイプをテスト）
            for change_type in ChangeType:
                change = Change(
                    code='test-001',
                    type=change_type,
                    payload='{"test": "data"}'
                )
                session.add(change)
            
            session.commit()
            
            # データが正常に挿入されたことを確認
            item_count = session.query(Item).count()
            assert item_count == 1
            
            change_count = session.query(Change).count()
            assert change_count == len(ChangeType)
            
            # PRICE_UPDATE変更イベントが存在することを確認
            price_update_change = session.query(Change).filter(
                Change.type == ChangeType.PRICE_UPDATE
            ).first()
            assert price_update_change is not None
            
        finally:
            session.close()
    
    def test_downgrade_safety(self):
        """ダウングレードの安全性テスト"""
        # 最新まで上げる
        command.upgrade(self.alembic_cfg, "head")
        
        # 1つ前のリビジョンにダウングレード
        script_dir = ScriptDirectory.from_config(self.alembic_cfg)
        revisions = list(script_dir.walk_revisions())
        
        if len(revisions) >= 2:
            previous_revision = revisions[1].revision
            
            # ダウングレードが例外を発生させないことを確認
            try:
                command.downgrade(self.alembic_cfg, previous_revision)
                # 再度アップグレード
                command.upgrade(self.alembic_cfg, "head")
            except Exception as e:
                pytest.fail(f"Migration downgrade/upgrade failed: {e}")
    
    def test_migration_repeatability(self):
        """マイグレーションの冪等性テスト"""
        # 最初のマイグレーション
        command.upgrade(self.alembic_cfg, "head")
        
        # 現在のリビジョンを取得
        with self.engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
        
        # 同じマイグレーションを再実行
        command.upgrade(self.alembic_cfg, "head")
        
        # リビジョンが変わっていないことを確認
        with self.engine.connect() as conn:
            context = MigrationContext.configure(conn)
            after_rev = context.get_current_revision()
            
        assert current_rev == after_rev
    
    def test_specific_price_update_revision(self):
        """PRICE_UPDATE リビジョンの特定テスト"""
        # db233a178353 リビジョンまでマイグレーション
        command.upgrade(self.alembic_cfg, "db233a178353")
        
        # データベースにテーブルが作成されていることを確認
        with self.engine.connect() as conn:
            # changesテーブルが存在し、PRICE_UPDATEが使用可能であることを確認
            Session = sessionmaker(bind=self.engine)
            session = Session()
            
            try:
                # テスト用アイテム作成
                test_item = Item(
                    code='price-test',
                    title='価格テスト商品',
                    price=2000,
                    in_stock=True
                )
                session.add(test_item)
                session.commit()
                
                # PRICE_UPDATE変更を作成
                price_change = Change(
                    code='price-test',
                    type=ChangeType.PRICE_UPDATE,
                    payload='{"old_price": 2000, "new_price": 2500}'
                )
                session.add(price_change)
                session.commit()
                
                # 正常に保存されたことを確認
                saved_change = session.query(Change).filter(
                    Change.type == ChangeType.PRICE_UPDATE
                ).first()
                assert saved_change is not None
                assert saved_change.code == 'price-test'
                
            finally:
                session.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])