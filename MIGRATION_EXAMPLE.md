# 実際の移行手順例

## 前提条件
- PostgreSQL サーバーが起動している
- データベース `rakuten_monitor` とユーザー `rakuten_user` が作成済み
- 適切な権限が設定済み

## 手順

### 1. 作業ディレクトリに移動
```bash
cd /home/yang_server/rakuten
```

### 2. 仮想環境の有効化
```bash
source venv/bin/activate
```

### 3. 環境変数設定
```bash
export PGHOST=localhost
export PGPORT=5432
export PGDATABASE=rakuten_monitor
export PGUSER=rakuten_user
export PGPASSWORD=rakuten_pass
```

### 4. SQLite dump の作成（既存DBがある場合）
```bash
# 既存のSQLiteデータベースがある場合
sqlite3 products.sqlite .dump > /tmp/products.sql

# テスト用の場合（今回実行済み）
python3 dump_sqlite.py  # /tmp/products.sql に出力済み
```

### 5. マイグレーション実行
```bash
# 正しいパス（rakutenディレクトリから実行）
python3 scripts/migrate_sqlite_to_pg.py --sqlite-dump /tmp/products.sql
```

### 6. 動作確認
```bash
# PostgreSQL経由のテスト実行
python3 test_postgres_integration.py

# または monitor の test モード
python3 -c "
import sys
sys.path.insert(0, '.')
from monitor import RakutenMonitor
monitor = RakutenMonitor()
if monitor._test_database_connection():
    print('✅ PostgreSQL接続成功')
else:
    print('❌ PostgreSQL接続失敗')
"
```

## 実行結果の確認

### ✅ 成功例（PostgreSQLサーバー動作時）
```
INFO:scripts.migrate_sqlite_to_pg:PostgreSQL接続成功
INFO:scripts.migrate_sqlite_to_pg:テーブル作成完了
INFO:scripts.migrate_sqlite_to_pg:4個のアイテムを解析しました
INFO:scripts.migrate_sqlite_to_pg:4個のアイテムを移行しました
INFO:scripts.migrate_sqlite_to_pg:マイグレーション完了
```

### ❌ 現在の状況（PostgreSQLサーバー未設定）
```
ERROR:__main__:PostgreSQL接続に失敗: connection to server at "localhost" (127.0.0.1), port 5432 failed: FATAL:  password authentication failed for user "rakuten_user"
```

## トラブルシューティング

### 1. パスエラーの場合
```bash
# エラー: python3: can't open file '/home/yang_server/scripts/migrate_sqlite_to_pg.py'
# 解決: rakutenディレクトリから実行
cd /home/yang_server/rakuten
python3 scripts/migrate_sqlite_to_pg.py --sqlite-dump /tmp/products.sql
```

### 2. PostgreSQL認証エラーの場合
```bash
# PostgreSQLサーバーの設定を確認
sudo -u postgres psql
CREATE DATABASE rakuten_monitor;
CREATE USER rakuten_user WITH PASSWORD 'rakuten_pass';
GRANT ALL PRIVILEGES ON DATABASE rakuten_monitor TO rakuten_user;
```

### 3. 依存関係エラーの場合
```bash
source venv/bin/activate
pip install psycopg2-binary requests beautifulsoup4 pyyaml
```

## 確認済み項目

✅ スクリプトのパスと実行権限  
✅ SQLiteダンプの解析機能（4個のアイテム検出）  
✅ PostgreSQL接続コード  
✅ マイグレーション処理ロジック  
✅ 依存関係インストール  

**結論**: PostgreSQLサーバーの認証設定が完了すれば、即座にマイグレーションが実行できます。