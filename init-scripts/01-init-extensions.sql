-- PostgreSQL 拡張の初期化
-- TimescaleDB拡張の有効化（TimescaleDBコンテナのみ）

DO $$
BEGIN
    -- TimescaleDBが利用可能かチェック
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb') THEN
        CREATE EXTENSION IF NOT EXISTS timescaledb;
        RAISE NOTICE 'TimescaleDB extension enabled';
    ELSE
        RAISE NOTICE 'TimescaleDB extension not available';
    END IF;
END
$$;

-- その他の有用な拡張
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- ログ出力
SELECT 'Database initialization completed' as status;