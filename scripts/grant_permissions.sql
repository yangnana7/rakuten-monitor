-- PostgreSQL権限付与スクリプト
-- rakuten_userにrakuten_monitorデータベースでの必要権限を付与

-- 基本的なスキーマ権限
GRANT CREATE ON SCHEMA public TO rakuten_user;
GRANT USAGE ON SCHEMA public TO rakuten_user;

-- 既存のテーブル・シーケンスへの権限
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO rakuten_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO rakuten_user;

-- 将来作成されるオブジェクトへのデフォルト権限
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO rakuten_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO rakuten_user;

-- データベース全体への接続権限（念のため）
GRANT CONNECT ON DATABASE rakuten_monitor TO rakuten_user;

-- 権限確認クエリ
SELECT 
    r.rolname,
    has_database_privilege(r.rolname, 'rakuten_monitor', 'CONNECT') as can_connect,
    has_schema_privilege(r.rolname, 'public', 'CREATE') as can_create_in_public,
    has_schema_privilege(r.rolname, 'public', 'USAGE') as can_use_public
FROM pg_roles r 
WHERE r.rolname = 'rakuten_user';

\echo 'PostgreSQL permissions granted successfully to rakuten_user!'