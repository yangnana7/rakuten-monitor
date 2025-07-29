-- 楽天商品監視システム データベーススキーマ
-- Phase 2: データベース設計

-- items: 現在の最新状態
CREATE TABLE items (
    code        TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    price       INTEGER,
    in_stock    BOOLEAN NOT NULL,
    first_seen  TIMESTAMPTZ NOT NULL,
    last_seen   TIMESTAMPTZ NOT NULL
);

-- changes: イベント履歴
CREATE TYPE change_type AS ENUM ('NEW','RESTOCK','TITLE_UPDATE','PRICE_UPDATE','SOLDOUT');
CREATE TABLE changes (
    id          BIGSERIAL PRIMARY KEY,
    code        TEXT REFERENCES items(code),
    type        change_type NOT NULL,
    payload     TEXT,                 -- 旧タイトル・価格など（JSON文字列）
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- runs: 各実行のメタ
CREATE TABLE runs (
    id          BIGSERIAL PRIMARY KEY,
    fetched_at  TIMESTAMPTZ NOT NULL,
    snapshot    TEXT                -- ファイルパス or JSONB
);

-- インデックス: 最新イベントの高速取得
CREATE INDEX idx_changes_code_occurred ON changes(code, occurred_at DESC);
CREATE INDEX idx_changes_type_occurred ON changes(type, occurred_at DESC);
CREATE INDEX idx_items_last_seen ON items(last_seen DESC);
CREATE INDEX idx_runs_fetched_at ON runs(fetched_at DESC);
