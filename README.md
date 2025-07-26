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

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 環境設定

`.env`ファイルを作成：

```env
# データベース設定
DATABASE_URL=sqlite:///rakuten_monitor.db

# Discord Webhook URL
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL

# 楽天商品ページ設定
LIST_URL=https://item.rakuten.co.jp/auc-p-entamestore/c/0000000174/?s=4
USER_AGENT=Mozilla/5.0 (X11; Linux x86_64) Gecko
```

### 3. データベース初期化

```bash
# マイグレーション実行
alembic upgrade head
```

## 使用方法

### 基本的な監視実行

```bash
# 1回の監視サイクルを実行
python monitor.py
```

### 個別スクリプトの実行

```bash
# 商品データ取得のみ
python fetch_items.py

# 差分検知のみ
python diff_items.py

# Discord通知テスト
python discord_notifier.py
```

### CLIオプション

```bash
# 差分検知の詳細オプション
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

## トラブルシューティング

### よくある問題

1. **Discord通知が送信されない**
   - `DISCORD_WEBHOOK_URL`が正しく設定されているか確認
   - `python discord_notifier.py`でテスト実行

2. **商品が取得できない**
   - ネットワーク接続を確認  
   - 楽天サイトの構造変更の可能性
   - `fetch_items.log`でエラー詳細を確認

3. **データベースエラー**
   - `alembic upgrade head`でマイグレーション実行
   - データベースファイルの権限確認

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