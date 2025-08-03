# Rakuten Monitor

楽天市場の商品在庫状況を監視し、Discord で通知するアプリケーション。

## 機能

- 楽天市場の商品ページから在庫情報を取得
- PostgreSQL データベースによる商品情報管理
- Discord webhook による在庫変更通知
- 設定ファイルによる柔軟な監視設定

## インストール

### 依存関係
```bash
pip install -r requirements.txt
```

### PostgreSQL 設定
PostgreSQL サーバーをインストールし、データベースを作成：

```sql
CREATE DATABASE rakuten_monitor;
CREATE USER rakuten_user WITH PASSWORD 'rakuten_pass';
GRANT ALL PRIVILEGES ON DATABASE rakuten_monitor TO rakuten_user;
```

### 環境変数
PostgreSQL 接続情報を設定：

```bash
export PGHOST=localhost
export PGPORT=5432
export PGDATABASE=rakuten_monitor
export PGUSER=rakuten_user
export PGPASSWORD=rakuten_pass
```

## 使用方法

### 基本的な使用方法
```python
from item_db import ItemDB
from monitor import RakutenMonitor

# データベース操作
with ItemDB() as db:
    item = db.get_item('item_code_123')
    if item:
        print(f"商品: {item['title']}, 価格: {item['price']}")

# 監視実行
monitor = RakutenMonitor()
monitor.run()
```

### データベース API

#### ItemDB クラス
```python
# 商品取得
item = db.get_item(item_code)  # dict | None

# 商品保存（アップサート）
db.save_item({
    'item_code': 'unique_code',
    'title': '商品名',
    'price': 1000,
    'status': '在庫あり'
})

# ステータス更新
db.update_status(item_code, '売り切れ')

# 全商品取得
all_items = db.get_all_items()

# 古いデータ削除
deleted_count = db.cleanup_old_items(days=30)
```

## マイグレーション

SQLite から PostgreSQL への移行については `scripts/README_migrate.md` を参照してください。

## 設定

### config.yaml 例
```yaml
database:
  host: localhost
  port: 5432
  database: rakuten_monitor
  user: rakuten_user
  password: rakuten_pass

discord:
  webhook_url: "https://discord.com/api/webhooks/..."

monitoring:
  interval: 300  # 5分間隔
  timeout: 30
```

## 開発

### テスト実行
```bash
# 基本テスト
pytest tests/

# PostgreSQL 統合テスト
export POSTGRES_TEST_ENABLED=1
pytest tests/test_item_db.py

# Chaos テスト（例外処理・通知堅牢性）
pytest tests/test_monitor_chaos.py -v

# 全テストスイート実行
pytest tests/ -v --tb=short
```

### Chaos テスト（障害シミュレーション）
```bash
# 1. モックテストでエラーハンドリング確認
pytest tests/test_monitor_chaos.py::TestLayoutChangeDetection -v
pytest tests/test_monitor_chaos.py::TestDatabaseConnectionError -v
pytest tests/test_monitor_chaos.py::TestDiscordNotificationError -v

# 2. 実際の無効URLでネットワークエラーテスト
python3 -m monitor --config chaos_config.json

# 3. systemd ログでエラー通知確認
journalctl -u rakuten-monitor -n 50 --no-pager

# 4. Prometheus Pushgateway起動（オプション）
docker run -d -p 9091:9091 prom/pushgateway
export PROM_PUSHGATEWAY_URL=http://localhost:9091
```

### ログレベル設定
```python
import logging
logging.basicConfig(level=logging.INFO)
```

## systemd統合 (本番デプロイ)

### 自動デプロイ
```bash
# root権限で実行
sudo ./deploy/install.sh
```

### 手動デプロイ
```bash
# 1. PostgreSQL設定
sudo -u postgres psql -c "CREATE DATABASE rakuten_monitor;"
sudo -u postgres psql -c "CREATE USER rakuten_user WITH PASSWORD 'rakuten_pass';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE rakuten_monitor TO rakuten_user;"

# 2. 環境変数設定
cp deploy/rakuten_env.template ~/.rakuten_env
chmod 600 ~/.rakuten_env

# 3. systemdユニット配置
sudo cp deploy/rakuten-monitor.service /etc/systemd/system/
sudo cp deploy/rakuten-monitor.timer /etc/systemd/system/
sudo systemctl daemon-reload

# 4. サービス開始
sudo systemctl enable --now rakuten-monitor.timer

# 5. 状態確認
systemctl status rakuten-monitor.timer
systemctl status rakuten-monitor.service
journalctl -u rakuten-monitor -f
```

### cron から systemd への移行
```bash
# 既存cronエントリ削除
crontab -e  # rakuten関連の行を手動削除
# または
crontab -l | grep -v rakuten | crontab -

# systemdタイマー確認
systemctl list-timers rakuten-monitor.timer
```

### トラブルシューティング
```bash
# ログ確認
journalctl -u rakuten-monitor --since "1 hour ago"

# サービス再起動
sudo systemctl restart rakuten-monitor.timer

# 手動実行テスト
sudo -u yang_server /usr/bin/python3 -m monitor --cron
```

## アーキテクチャ

- `item_db.py`: PostgreSQL データベース管理
- `monitor.py`: 楽天市場監視ロジック
- `discord_notifier.py`: Discord 通知機能
- `config_loader.py`: 設定ファイル読み込み
- `exceptions.py`: カスタム例外定義
- `deploy/`: systemdユニットとデプロイスクリプト

## ライセンス

MIT License