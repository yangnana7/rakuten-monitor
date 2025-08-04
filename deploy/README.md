# Rakuten Monitor デプロイメントガイド

## 概要
このディレクトリには、Rakuten Monitor を本番環境にデプロイするためのファイルが含まれています。

## ファイル構成
```
deploy/
├── README.md                     # このファイル
├── install.sh                    # 自動デプロイスクリプト
├── rakuten-monitor.service       # systemd サービスファイル
├── rakuten-monitor.timer         # systemd タイマーファイル
├── rakuten-bot.service           # Discord Bot systemd サービス
└── rakuten_env.template          # 環境変数テンプレート
```

## 自動デプロイ（推奨）

### 実行方法
```bash
cd /home/yang_server/rakuten
sudo ./deploy/install.sh
```

### 自動実行される処理
1. **前提条件チェック**: PostgreSQL、Python3の確認
2. **PostgreSQL設定**: データベース・ユーザー作成、pg_hba.conf更新
3. **cron クリーンアップ**: 既存のrakuten関連crontabエントリ削除
4. **環境変数設定**: ~/.rakuten_env ファイル作成
5. **systemdユニット配置**: サービス・タイマー・Discord Botファイル配置
6. **ログローテート設定**: /etc/logrotate.d/rakuten-monitor 作成
7. **接続テスト**: PostgreSQL・Python環境の動作確認

### 実行後の確認
```bash
# タイマー状況確認
systemctl status rakuten-monitor.timer

# 最近の実行ログ確認
journalctl -u rakuten-monitor --since "1 hour ago"

# 次回実行予定確認
systemctl list-timers rakuten-monitor.timer
```

## 手動デプロイ

### 1. PostgreSQL 設定
```bash
# データベース作成
sudo -u postgres psql << 'EOF'
CREATE DATABASE rakuten_monitor;
CREATE USER rakuten_user WITH PASSWORD 'rakuten_pass';
GRANT ALL PRIVILEGES ON DATABASE rakuten_monitor TO rakuten_user;
EOF

# pg_hba.conf 編集
sudo nano /etc/postgresql/16/main/pg_hba.conf
# 以下を追加:
# host    rakuten_monitor    rakuten_user    127.0.0.1/32    scram-sha-256

# PostgreSQL再読み込み
sudo systemctl reload postgresql
```

### 2. 環境変数設定
```bash
cp deploy/rakuten_env.template ~/.rakuten_env
chmod 600 ~/.rakuten_env

# 必要に応じてパスワード等を編集
nano ~/.rakuten_env
```

### 3. systemd ユニット配置
```bash
sudo cp deploy/rakuten-monitor.service /etc/systemd/system/
sudo cp deploy/rakuten-monitor.timer /etc/systemd/system/
sudo systemctl daemon-reload
```

### 4. 既存 cron エントリ削除
```bash
# rakuten関連エントリを削除
crontab -l | grep -v rakuten | crontab -
```

### 5. サービス開始
```bash
sudo systemctl enable --now rakuten-monitor.timer
```

## Discord Bot 設定

### Bot Token 設定
```bash
# 環境変数ファイルを編集
nano ~/.rakuten_env

# DISCORD_BOT_TOKEN= の行に Bot Token を設定
DISCORD_BOT_TOKEN=your_discord_bot_token_here
```

### Bot サービス操作
```bash
# Bot 開始
sudo systemctl start rakuten-bot.service

# Bot 停止
sudo systemctl stop rakuten-bot.service

# Bot 状況確認
systemctl status rakuten-bot.service

# Bot ログ確認
journalctl -u rakuten-bot -f
```

### Bot 招待とテスト
1. **Bot招待URL生成**:
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=2048&scope=bot
   ```

2. **コマンドテスト**:
   - `!status` - システム状況確認
   - `!status -help` - ヘルプ表示
   - `!ping` - 接続テスト

### 環境変数更新と再起動
```bash
# 1. 環境変数ファイル編集
nano ~/.rakuten_env

# 2. Bot サービス再起動
sudo systemctl restart rakuten-bot.service

# 3. 監視サービス再起動（必要に応じて）
sudo systemctl restart rakuten-monitor.timer
```

## 運用・保守

### 状況確認コマンド
```bash
# タイマー状況
systemctl status rakuten-monitor.timer --no-pager

# サービス状況
systemctl status rakuten-monitor.service --no-pager

# Discord Bot 状況
systemctl status rakuten-bot.service --no-pager

# ログ確認
journalctl -u rakuten-monitor -f
journalctl -u rakuten-bot -f

# 次回実行予定
systemctl list-timers rakuten-monitor.timer
```

### メンテナンス操作
```bash
# タイマー停止
sudo systemctl stop rakuten-monitor.timer

# タイマー開始
sudo systemctl start rakuten-monitor.timer

# 設定再読み込み
sudo systemctl daemon-reload
sudo systemctl restart rakuten-monitor.timer

# 手動実行（テスト）
sudo -u yang_server bash -c 'cd /home/yang_server/rakuten && source .rakuten_env && python3 -m monitor --test'
```

### ログファイル
- **systemdログ**: `journalctl -u rakuten-monitor`
- **ローテートログ**: `/var/log/rakuten-monitor/` (今後実装予定)

## トラブルシューティング

### PostgreSQL接続エラー
```bash
# 接続テスト
PGPASSWORD=rakuten_pass psql -h localhost -U rakuten_user -d rakuten_monitor -c "\dt"

# ユーザー・データベース確認
sudo -u postgres psql -c "\du"
sudo -u postgres psql -c "\l"

# pg_hba.conf確認
sudo cat /etc/postgresql/16/main/pg_hba.conf | grep rakuten
```

### サービス起動失敗
```bash
# 詳細ログ確認
journalctl -u rakuten-monitor --since "1 hour ago" --no-pager

# 手動実行での問題特定
sudo -u yang_server bash -c 'cd /home/yang_server/rakuten && source ~/.rakuten_env && python3 -m monitor --cron'

# 権限確認
ls -la /home/yang_server/rakuten/
ls -la ~/.rakuten_env
```

### 依存関係エラー
```bash
# Python環境確認
sudo -u yang_server bash -c 'cd /home/yang_server/rakuten && source venv/bin/activate && pip list'

# 必要パッケージ再インストール
sudo -u yang_server bash -c 'cd /home/yang_server/rakuten && source venv/bin/activate && pip install -r requirements.txt'
```

## セキュリティ考慮事項

1. **環境変数ファイル**: `~/.rakuten_env` は 600 権限で保護
2. **systemd権限**: サービスは yang_server ユーザーで実行
3. **PostgreSQL認証**: scram-sha-256 認証方式使用
4. **ネットワーク**: 127.0.0.1 ローカル接続のみ許可

## 設定カスタマイズ

### 実行間隔変更
`rakuten-monitor.timer` の `OnUnitActiveSec` を編集:
```ini
[Timer]
OnUnitActiveSec=10min  # 10分間隔に変更
```

### 環境変数追加
`~/.rakuten_env` に追加設定:
```bash
# カスタム設定
CUSTOM_SETTING=value
```

### ログレベル変更
`~/.rakuten_env` で設定:
```bash
LOGLEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```