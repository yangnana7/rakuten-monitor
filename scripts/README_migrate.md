# SQLite から PostgreSQL へのマイグレーション手順

## 概要
Rakuten Monitor アプリケーションのデータベースを SQLite から PostgreSQL に移行するためのガイドです。

## 前提条件

### PostgreSQL サーバー準備
1. PostgreSQL サーバーをインストール・起動
2. データベースとユーザーを作成

```sql
-- PostgreSQL サーバーで実行
CREATE DATABASE rakuten_monitor;
CREATE USER rakuten_user WITH PASSWORD 'rakuten_pass';
GRANT ALL PRIVILEGES ON DATABASE rakuten_monitor TO rakuten_user;
```

### 環境変数設定
PostgreSQL 接続情報を環境変数で設定：

```bash
export PGHOST=localhost
export PGPORT=5432
export PGDATABASE=rakuten_monitor
export PGUSER=rakuten_user
export PGPASSWORD=rakuten_pass
```

## マイグレーション手順

### 1. 依存関係インストール
```bash
pip install -r requirements.txt
```

### 2. SQLite データのダンプ作成
既存の SQLite データベースからダンプを作成：

```bash
sqlite3 rakuten_items.db .dump > sqlite_dump.sql
```

### 3. マイグレーション実行
作成したダンプファイルを使用してマイグレーション：

```bash
python scripts/migrate_sqlite_to_pg.py --sqlite-dump sqlite_dump.sql
```

### 4. 動作確認
PostgreSQL に正しくデータが移行されたか確認：

```bash
psql -h localhost -U rakuten_user -d rakuten_monitor -c "SELECT COUNT(*) FROM items;"
```

## データベース構造

### PostgreSQL テーブル構造
```sql
CREATE TABLE items (
    item_code TEXT PRIMARY KEY,
    title TEXT,
    price INTEGER,
    status TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### SQLite から PostgreSQL への変換

| SQLite 列 | PostgreSQL 列 | 変換内容 |
|-----------|---------------|----------|
| url + product_id | item_code | URL と商品ID を結合してユニークキーに |
| name | title | 列名変更 |
| price | price | 文字列から整数に変換 |
| status | status | そのまま |
| last_updated | updated_at | 列名変更 |

## トラブルシューティング

### 接続エラー
```
PostgreSQL接続に失敗: connection to server failed
```

**解決方法:**
- PostgreSQL サーバーが起動しているか確認
- 環境変数が正しく設定されているか確認
- ファイアウォール設定を確認

### 権限エラー
```
ERROR: permission denied for table items
```

**解決方法:**
```sql
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO rakuten_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO rakuten_user;
```

### データ形式エラー
```
invalid input syntax for type integer
```

**解決方法:**
- SQLite ダンプファイルの価格データが正しい形式か確認
- 必要に応じてマイグレーションスクリプトの `_convert_price` メソッドを調整

## 設定例

### Docker Compose 使用例
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: rakuten_monitor
      POSTGRES_USER: rakuten_user
      POSTGRES_PASSWORD: rakuten_pass
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### systemd 環境変数設定例
```ini
[Service]
Environment=PGHOST=localhost
Environment=PGPORT=5432
Environment=PGDATABASE=rakuten_monitor
Environment=PGUSER=rakuten_user
Environment=PGPASSWORD=rakuten_pass
```

## 注意事項

1. **データバックアップ**: マイグレーション前に必ず既存データのバックアップを取得
2. **テスト環境**: 本番環境での実行前にテスト環境で動作確認
3. **パフォーマンス**: 大量データの場合は `page_size` パラメータを調整
4. **セキュリティ**: 本番環境では強力なパスワードを使用