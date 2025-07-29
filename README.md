# 楽天商品監視システム

楽天市場の特定ショップ商品を監視し、新商品・再入荷・価格変更などを自動検知してDiscordに通知するシステムです。

## 概要

- **対象ショップ**: P Entertainment Store (auc-p-entamestore)
- **商品カテゴリ**: パチスロ小役カウンター「勝ち勝ちくん」シリーズ
- **機能**: NEW・RESTOCK・TITLE_UPDATE・PRICE_UPDATE・SOLDOUT検知
- **通知**: Discord Webhook
- **データベース**: SQLite（PostgreSQL対応可能）

## Phase 2 完了機能

✅ **データベース設計**
- items, changes, runs テーブル
- Alembic マイグレーション管理

✅ **改善された取得スクリプト**
- エラー処理・リトライ機能
- 型ヒント・ログ出力
- 環境変数による設定管理

✅ **拡張された差分検知**
- SOLDOUT検知追加
- CLIオプション対応
- ファイルソート改善

✅ **DB連携監視システム**
- データ永続化
- 変更履歴管理
- Discord自動通知

## セットアップ

### 開発手順 (オフライン)
```bash
git clone ssh://yang_server/srv/git/rakuten-monitor.git
cd rakuten-monitor
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pre-commit run --all-files      # フルチェック
pytest -q
```

### 1. 仮想環境の作成と依存関係のインストール

```bash
# 仮想環境作成
python -m venv .venv

# 仮想環境有効化 (Linux/Mac)
source .venv/bin/activate

# 仮想環境有効化 (Windows)
.venv\Scripts\activate

# 依存関係インストール
pip install -r requirements.txt
```

### 2. 環境設定

`.env`ファイルを作成：

```env
# データベース設定
DATABASE_URL=sqlite:///rakuten_monitor.db

# Discord Webhook URL
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL

# Discord Alert Webhook URL (for error alerts)
ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ALERT_WEBHOOK_URL

# 楽天商品ページ設定
LIST_URL=https://item.rakuten.co.jp/auc-p-entamestore/c/0000000174/?s=4
USER_AGENT=Mozilla/5.0 (X11; Linux x86_64) Gecko

# Prometheusメトリクス設定
METRICS_PORT=9100
```

### 3. PostgreSQL使用時の追加設定

Docker secretsを使用する場合：

```bash
# PostgreSQLパスワードファイルを作成
echo "your_secure_password" > postgres_password.txt
chmod 600 postgres_password.txt

# Docker Compose起動
docker-compose up -d
```

### 4. データベース初期化

```bash
# マイグレーション実行
alembic upgrade head
```

## 使用方法

### CLIオプション

```bash
# Discord Webhook テスト
python -m monitor --test-webhook

# 1回の監視サイクルを実行
python -m monitor --once

# Cronモード（10分間隔で無限ループ、デフォルト）
python -m monitor --cron
python -m monitor  # --cronと同じ

# ヘルプ表示
python -m monitor --help
```

### 個別スクリプトの実行

```bash
# 商品データ取得のみ
python fetch_items.py

# 差分検知のみ
python diff_items.py

# Discord通知テスト（旧方式）
python discord_notifier.py

# エラーアラートテスト
python error_handler.py
```

### 差分検知の詳細オプション

```bash
python diff_items.py --help
python diff_items.py --latest          # 最新スナップショットを表示
python diff_items.py --snapshots-dir custom_dir  # カスタムディレクトリ
```

## Cron設定（自動実行）

10分間隔での自動監視設定例：

```bash
# crontab -e で以下を追加
*/10 * * * * /usr/bin/python3 /path/to/rakuten/monitor.py >> /var/log/rakuten_monitor.log 2>&1
```

環境変数を使用する場合：

```bash
*/10 * * * * cd /path/to/rakuten && /usr/bin/python3 monitor.py >> /var/log/rakuten_monitor.log 2>&1
```

## ファイル構成

```
rakuten/
├── monitor.py              # メイン監視スクリプト
├── fetch_items.py          # 商品データ取得
├── diff_items.py           # 差分検知
├── discord_notifier.py     # Discord通知
├── models.py               # データベースモデル
├── schema.sql              # PostgreSQL用スキーマ
├── requirements.txt        # Python依存関係
├── .env                    # 環境設定（要作成）
├── .gitignore             # Git除外設定
├── alembic.ini            # Alembicマイグレーション設定
├── alembic/               # マイグレーションファイル
└── snapshots/             # スナップショットファイル（レガシー）
```

## Discord通知フォーマット

検知された変更は以下の形式でDiscordに通知されます：

- 🆕 **NEW**: 新商品発見
- 🔄 **RESTOCK**: 再入荷
- 📝 **TITLE_UPDATE**: タイトル変更
- 💰 **PRICE_UPDATE**: 価格変更
- ❌ **SOLDOUT**: 売り切れ

各通知には商品名、価格、在庫状況、URLが含まれます。

## データベーススキーマ

### items テーブル
```sql
code        TEXT PRIMARY KEY    -- 商品コード
title       TEXT NOT NULL       -- 商品タイトル
price       INTEGER              -- 価格
in_stock    BOOLEAN NOT NULL    -- 在庫状況
first_seen  TIMESTAMPTZ NOT NULL -- 初回検出日時
last_seen   TIMESTAMPTZ NOT NULL -- 最終確認日時
```

### changes テーブル
```sql
id          BIGSERIAL PRIMARY KEY -- 変更ID
code        TEXT REFERENCES items(code) -- 商品コード
type        change_type NOT NULL  -- 変更タイプ
payload     JSONB                 -- 追加情報
occurred_at TIMESTAMPTZ NOT NULL  -- 発生日時
```

### runs テーブル
```sql
id          BIGSERIAL PRIMARY KEY -- 実行ID
fetched_at  TIMESTAMPTZ NOT NULL  -- 実行日時
snapshot    TEXT                  -- スナップショットデータ
```

## ログ確認

```bash
# 監視ログ
tail -f monitor.log

# 取得ログ
tail -f fetch_items.log
```

## 障害対応・トラブルシューティング

### 緊急対応フローチャート

1. **システム停止時の復旧手順**
   ```bash
   # 1. システム状態確認
   sudo systemctl status rakuten-monitor.timer
   sudo systemctl status rakuten-monitor.service

   # 2. ログ確認
   journalctl -u rakuten-monitor.service -n 50
   tail -f /var/log/rakuten_monitor.log

   # 3. 手動実行テスト
   cd /home/ubuntu/rakutenApp
   python monitor.py

   # 4. サービス再起動
   sudo systemctl restart rakuten-monitor.timer
   ```

2. **データベース障害対応**
   ```bash
   # SQLiteファイル破損の場合
   cd /home/ubuntu/rakutenApp
   cp rakuten_monitor.db rakuten_monitor.db.backup
   sqlite3 rakuten_monitor.db ".recover" | sqlite3 rakuten_monitor_recovered.db
   mv rakuten_monitor_recovered.db rakuten_monitor.db

   # 権限問題の場合
   sudo chown ubuntu:ubuntu rakuten_monitor.db
   chmod 664 rakuten_monitor.db
   ```

3. **ネットワーク・サイト障害対応**
   ```bash
   # 楽天サイト接続テスト
   curl -I "https://item.rakuten.co.jp/auc-p-entamestore/c/0000000174/?s=4"

   # DNS解決確認
   nslookup item.rakuten.co.jp

   # プロキシ・ファイアウォール確認
   wget --spider --timeout=30 "https://item.rakuten.co.jp/auc-p-entamestore/c/0000000174/?s=4"
   ```

### よくある問題と解決方法

| 症状 | 原因 | 診断方法 | 対処方法 |
|------|------|----------|----------|
| Discord に通知が来ない | Webhook URL設定エラー | `python discord_notifier.py`でテスト | `.env`ファイルの`DISCORD_WEBHOOK_URL`を確認・修正 |
| | Discord Rate Limit | ログで`429`エラー確認 | 5-10分待機後に自動復旧 |
| | ネットワーク障害 | `curl`でWebhook URLテスト | ネットワーク設定確認、プロキシ設定 |
| 商品取得ができない | 楽天サイト構造変更 | `fetch_items.log`でKeyError確認 | `fetch_items.py`のセレクタ修正 |
| | アクセス制限・IP ブロック | HTTP 403/429エラー | User-Agent変更、IP変更、待機時間追加 |
| | ネットワーク障害 | TimeoutError、ConnectionError | ネットワーク接続確認、DNS設定確認 |
| データベースエラー | マイグレーション未実行 | `alembic current`で確認 | `alembic upgrade head`実行 |
| | SQLiteファイル破損 | SQLiteエラーメッセージ | 上記のデータベース復旧手順実行 |
| | 権限不足 | Permission Deniedエラー | ファイル権限とオーナー確認・修正 |
| systemdサービス起動しない | 環境変数ファイル不備 | `systemctl status`でエラー確認 | `/etc/rakuten_monitor.env`確認・修正 |
| | Python仮想環境パス間違い | ExecStartパス確認 | `rakuten-monitor.service`のパス修正 |
| | 作業ディレクトリ間違い | WorkingDirectory確認 | サービスファイルのディレクトリパス修正 |
| Prometheusメトリクス表示されない | メトリクスサーバー起動失敗 | `curl localhost:8000/metrics` | ポート8000の使用状況確認、ファイアウォール設定 |
| | ポート競合 | `netstat -tulpn \| grep 8000` | 環境変数`PROMETHEUS_PORT`で別ポート指定 |

### 定期メンテナンス

#### 毎日の確認事項
```bash
# 1. システム稼働状況
sudo systemctl is-active rakuten-monitor.timer
curl -s http://localhost:8000/metrics | grep rakuten_last_run_status

# 2. ログファイルサイズ確認
ls -lh /var/log/rakuten_monitor.log
ls -lh rakuten_monitor.log*

# 3. データベースサイズ確認
ls -lh rakuten_monitor.db*
```

#### 週次メンテナンス
```bash
# 1. ログローテーション確認
sudo logrotate -f /etc/logrotate.d/rakuten_monitor

# 2. データベースバックアップ
sqlite3 rakuten_monitor.db ".backup backup_$(date +%Y%m%d).db"

# 3. 依存関係アップデート確認
pip list --outdated
```

#### 月次メンテナンス
```bash
# 1. システムアップデート
sudo apt update && sudo apt upgrade

# 2. 古いログファイル削除
find . -name "*.log.*" -mtime +30 -delete

# 3. 古いバックアップファイル削除
find . -name "backup_*.db" -mtime +90 -delete

# 4. データベース最適化
sqlite3 rakuten_monitor.db "VACUUM;"
```

### パフォーマンス監視

#### 重要なメトリクス
- `rakuten_items_fetched_total`: 取得商品数の推移
- `rakuten_run_duration_seconds`: 実行時間の監視
- `rakuten_last_run_status`: 最新実行の成功/失敗
- `rakuten_changes_detected_total`: 変更検知数の統計

#### アラート設定推奨値
```bash
# 10分以上実行されていない場合
rakuten_last_run_timestamp < (now() - 600)

# 実行が連続3回失敗している場合
rakuten_last_run_status == 0

# 実行時間が通常の3倍を超えている場合
rakuten_run_duration_seconds > 90
```

### 災害復旧計画

#### データバックアップ戦略
1. **自動バックアップ**: 毎日午前3時にデータベースバックアップ
2. **設定ファイルバックアップ**: `/etc/rakuten_monitor.env`等の定期保存
3. **コードリポジトリ**: GitHubでのソースコード管理

#### 復旧手順
1. **サーバー全損時**: 新サーバーでの環境構築手順書実行
2. **データベース復旧**: 最新バックアップからのリストア
3. **設定復旧**: 環境変数・systemdサービスの再設定
4. **動作確認**: 手動実行→自動実行→Discord通知テスト

### 連絡体制

#### 障害レベル定義
- **レベル1 (軽微)**: 1-2回の実行失敗、自動復旧見込み
- **レベル2 (中程度)**: 連続失敗、手動対応が必要
- **レベル3 (重大)**: システム停止、即座の対応が必要

#### エスカレーション
1. **レベル1**: システムログ記録のみ
2. **レベル2**: Discord #alerts チャンネルに通知
3. **レベル3**: Discord通知 + メール通知（設定されている場合）

## 開発・カスタマイズ

### PostgreSQL使用時

`.env`で以下のように設定：

```env
DATABASE_URL=postgresql://user:password@localhost:5432/rakuten_monitor
```

### 対象ショップの変更

1. `.env`の`LIST_URL`を変更
2. `fetch_items.py`のセレクタ調整が必要な場合あり

## Phase 2 完了報告

Phase 2「データベース設計」の全タスクが完了しました：

- ✅ PostgreSQL/SQLite対応データベース設計
- ✅ Alembicマイグレーション管理
- ✅ 改善されたスクレイピング機能
- ✅ 拡張された差分検知
- ✅ Discord Webhook自動通知
- ✅ 本番運用対応のmonitor.py

Phase 3「モニター・通知」への準備が完了しています。

## 監視・運用ガイド

### Prometheusメトリクス

システムは以下のメトリクスを`http://localhost:9100/metrics`で公開します：

```
rakuten_items_fetched_total      # 取得した商品数
rakuten_changes_detected_total   # 検出した変更数（タイプ別）
rakuten_run_duration_seconds     # 実行時間
rakuten_fetch_duration_seconds   # フェッチ時間（方法別）
rakuten_last_run_status          # 最終実行ステータス
rakuten_discord_notifications_total  # Discord通知数
```

### Grafanaダッシュボード設定

#### 1. Prometheusデータソース追加
```json
{
  "name": "Prometheus",
  "type": "prometheus",
  "url": "http://localhost:9090",
  "access": "proxy"
}
```

#### 2. 推奨パネル設定

**商品監視状況パネル**
```json
{
  "title": "商品監視状況",
  "type": "stat",
  "targets": [
    {
      "expr": "rakuten_items_fetched_total",
      "legendFormat": "総取得商品数"
    },
    {
      "expr": "sum(rakuten_changes_detected_total)",
      "legendFormat": "総変更検出数"
    }
  ]
}
```

**実行時間トレンドパネル**
```json
{
  "title": "実行時間トレンド",
  "type": "graph",
  "targets": [
    {
      "expr": "rakuten_run_duration_seconds",
      "legendFormat": "実行時間"
    }
  ]
}
```

**変更タイプ別統計パネル**
```json
{
  "title": "変更タイプ別統計",
  "type": "piechart",
  "targets": [
    {
      "expr": "rakuten_changes_detected_total",
      "legendFormat": "{{change_type}}"
    }
  ]
}
```

#### 3. アラート設定例

**監視失敗アラート**
```yaml
alert:
  name: "Rakuten Monitor Failed"
  condition: "rakuten_last_run_status == 0"
  for: "15m"
  annotations:
    summary: "楽天監視システムが15分間失敗しています"
    description: "監視システムの確認が必要です"
```

### Cloudflare対策トラブルシューティング

#### 問題の症状
- HTTP 403 Forbidden エラー
- HTTP 429 Too Many Requests エラー
- "Checking your browser" メッセージ
- CloudFlare Challenge画面

#### 対策手順

**1. User-Agentの調整**
```env
USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
```

**2. リクエスト間隔の調整**
```python
import time
time.sleep(5)  # 5秒待機
```

**3. cloudscraper設定の調整**
```python
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    },
    delay=10
)
```

**4. Playwriteフォールバック確認**
```bash
# Playwright browserのインストール
playwright install chromium
```

#### エラー別対処法

| エラー | 原因 | 対処法 |
|--------|------|--------|
| 403 Forbidden | User-Agent検出 | USER_AGENT環境変数を更新 |
| 429 Too Many Requests | レート制限 | 実行間隔を延長（10-15分） |
| Cloudflare Challenge | Bot検出 | Playwright fallbackを確認 |
| SSL Error | 証明書問題 | `verify=False`を一時的に設定 |

#### 予防的設定

**cron設定での間隔調整**
```bash
# 10分間隔から15分間隔に変更
*/15 * * * * /usr/bin/python3 /path/to/monitor.py
```

**ログ監視設定**
```bash
# エラーログの監視
tail -f /var/log/rakuten_monitor.log | grep -E "(403|429|Cloudflare)"
```

#### よくある質問

**Q: 403エラーが頻発します**
A: User-Agentを最新のブラウザに更新し、実行間隔を延長してください。

**Q: Playwrightが動作しません**
A: `playwright install`でブラウザがインストールされているか確認してください。

**Q: すべての方法が失敗します**
A: 楽天側でアクセス制限が強化された可能性があります。数日間隔を空けて再試行してください。

### Redis Watchdog設定

Redis pub/sub接続の自動復旧機能が含まれています：

```env
REDIS_URL=redis://localhost:6379
```

**設定確認**
```bash
redis-cli ping  # Redis接続確認
```

**監視ログ**
```bash
grep "Redis" /var/log/rakuten_monitor.log
```

## ライセンス

このプロジェクトは研究・個人利用目的で作成されています。商用利用時は楽天市場の利用規約を遵守してください。
