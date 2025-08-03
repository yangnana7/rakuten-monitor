#!/bin/bash
set -euo pipefail

# Rakuten Monitor Deployment Script
echo "🚀 Rakuten Monitor デプロイメントスクリプト"

# 色付きログ関数
log_info() { echo -e "\033[32m[INFO]\033[0m $1"; }
log_warn() { echo -e "\033[33m[WARN]\033[0m $1"; }
log_error() { echo -e "\033[31m[ERROR]\033[0m $1"; }

# 前提条件チェック
check_prerequisites() {
    log_info "前提条件をチェック中..."
    
    # root権限チェック
    if [[ $EUID -ne 0 ]]; then
        log_error "このスクリプトはroot権限で実行してください"
        exit 1
    fi
    
    # PostgreSQLサービスチェック
    if ! systemctl is-active --quiet postgresql; then
        log_warn "PostgreSQLサービスが動作していません"
        log_info "PostgreSQLを開始しています..."
        systemctl start postgresql
    fi
    
    # 必要なコマンドチェック
    for cmd in systemctl psql python3; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "必要なコマンドが見つかりません: $cmd"
            exit 1
        fi
    done
}

# PostgreSQL設定
setup_postgresql() {
    log_info "PostgreSQL設定を開始..."
    
    # データベースとユーザー作成
    sudo -u postgres psql << 'EOF'
-- データベース作成
DROP DATABASE IF EXISTS rakuten_monitor;
CREATE DATABASE rakuten_monitor;

-- ユーザー作成
DROP USER IF EXISTS rakuten_user;
CREATE USER rakuten_user WITH PASSWORD 'rakuten_pass';

-- 権限付与
GRANT ALL PRIVILEGES ON DATABASE rakuten_monitor TO rakuten_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO rakuten_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO rakuten_user;

-- 接続テスト
\du
\l
EOF

    # pg_hba.conf設定
    local PG_VERSION=$(sudo -u postgres psql -t -c "SELECT version();" | grep -oP 'PostgreSQL \K[0-9]+')
    local PG_HBA_CONF="/etc/postgresql/${PG_VERSION}/main/pg_hba.conf"
    
    if [[ -f "$PG_HBA_CONF" ]]; then
        log_info "pg_hba.conf を更新中..."
        
        # バックアップ作成
        cp "$PG_HBA_CONF" "${PG_HBA_CONF}.bak.$(date +%Y%m%d_%H%M%S)"
        
        # rakuten_user用のエントリを追加
        if ! grep -q "rakuten_user" "$PG_HBA_CONF"; then
            echo "# Rakuten Monitor Database Access" >> "$PG_HBA_CONF"
            echo "host    rakuten_monitor    rakuten_user    127.0.0.1/32    scram-sha-256" >> "$PG_HBA_CONF"
            log_info "pg_hba.conf にエントリを追加しました"
        else
            log_info "pg_hba.conf にエントリが既に存在します"
        fi
        
        # PostgreSQL設定再読み込み
        systemctl reload postgresql
        log_info "PostgreSQL設定を再読み込みしました"
    else
        log_warn "pg_hba.conf が見つかりません: $PG_HBA_CONF"
    fi
}

# 既存cron削除
cleanup_cron() {
    log_info "既存のcron設定をクリーンアップ中..."
    
    # yang_serverユーザーのcrontabから rakuten 関連エントリを削除
    if sudo -u yang_server crontab -l 2>/dev/null | grep -q rakuten; then
        sudo -u yang_server crontab -l 2>/dev/null | grep -v rakuten | sudo -u yang_server crontab -
        log_info "既存のrakuten crontabエントリを削除しました"
    else
        log_info "削除すべきcrontabエントリはありませんでした"
    fi
}

# systemdユニット配置
install_systemd_units() {
    log_info "systemdユニットをインストール中..."
    
    # サービスファイルとタイマーファイルをコピー
    cp deploy/rakuten-monitor.service /etc/systemd/system/
    cp deploy/rakuten-monitor.timer /etc/systemd/system/
    
    # Discord Botサービスもコピー
    if [[ -f "deploy/rakuten-bot.service" ]]; then
        cp deploy/rakuten-bot.service /etc/systemd/system/
        chmod 644 /etc/systemd/system/rakuten-bot.service
        log_info "Discord Botサービスファイルをコピーしました"
    fi
    
    # 権限設定
    chmod 644 /etc/systemd/system/rakuten-monitor.service
    chmod 644 /etc/systemd/system/rakuten-monitor.timer
    
    # systemd再読み込み
    systemctl daemon-reload
    
    # サービス有効化と開始
    systemctl enable rakuten-monitor.timer
    systemctl start rakuten-monitor.timer
    
    # Discord Botサービス有効化（手動開始）
    if systemctl list-unit-files | grep -q "rakuten-bot.service"; then
        systemctl enable rakuten-bot.service
        log_info "Discord Botサービスを有効化しました（手動開始が必要）"
        log_warn "Bot Tokenを設定後、'systemctl start rakuten-bot' でBotを開始してください"
    fi
    
    log_info "systemdユニットのインストールが完了しました"
}

# 環境変数ファイル設定
setup_environment() {
    log_info "環境変数ファイルを設定中..."
    
    local ENV_FILE="/home/yang_server/.rakuten_env"
    
    if [[ ! -f "$ENV_FILE" ]]; then
        cp deploy/rakuten_env.template "$ENV_FILE"
        chown yang_server:yang_server "$ENV_FILE"
        chmod 600 "$ENV_FILE"
        log_info "環境変数ファイルを作成しました: $ENV_FILE"
    else
        log_info "環境変数ファイルが既に存在します: $ENV_FILE"
    fi
}

# ログローテート設定
setup_log_rotation() {
    log_info "ログローテート設定を作成中..."
    
    cat > /etc/logrotate.d/rakuten-monitor << 'EOF'
# Rakuten Monitor ログローテート設定
/var/log/rakuten-monitor/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 yang_server yang_server
    su yang_server yang_server
    postrotate
        systemctl reload-or-restart rsyslog > /dev/null 2>&1 || true
    endscript
}
EOF

    # ログディレクトリ作成
    mkdir -p /var/log/rakuten-monitor
    chown yang_server:yang_server /var/log/rakuten-monitor
    chmod 755 /var/log/rakuten-monitor
    
    log_info "ログローテート設定を作成しました"
}

# 接続テスト
test_connections() {
    log_info "接続テストを実行中..."
    
    # PostgreSQL接続テスト
    if sudo -u yang_server PGPASSWORD=rakuten_pass psql -h localhost -U rakuten_user -d rakuten_monitor -c "\dt" > /dev/null 2>&1; then
        log_info "✅ PostgreSQL接続テスト成功"
    else
        log_error "❌ PostgreSQL接続テスト失敗"
        return 1
    fi
    
    # Python環境テスト
    if sudo -u yang_server bash -c 'cd /home/yang_server/rakuten && source venv/bin/activate && python3 -c "from item_db import ItemDB; print(\"Python環境OK\")"' > /dev/null 2>&1; then
        log_info "✅ Python環境テスト成功"
    else
        log_error "❌ Python環境テスト失敗"
        return 1
    fi
}

# メイン実行
main() {
    log_info "=== Rakuten Monitor デプロイメント開始 ==="
    
    check_prerequisites
    setup_postgresql
    cleanup_cron
    setup_environment
    install_systemd_units
    setup_log_rotation
    test_connections
    
    log_info "=== デプロイメント完了 ==="
    log_info ""
    log_info "次のコマンドでサービス状況を確認できます:"
    log_info "  systemctl status rakuten-monitor.timer"
    log_info "  systemctl status rakuten-monitor.service"
    log_info "  systemctl status rakuten-bot.service"
    log_info "  journalctl -u rakuten-monitor -f"
    log_info "  journalctl -u rakuten-bot -f"
    log_info ""
    log_info "🤖 Discord Bot設定:"
    log_info "  1. ~/.rakuten_env ファイルを編集してDISCORD_BOT_TOKENを設定"
    log_info "  2. systemctl start rakuten-bot でBotを開始"
    log_info "  3. Bot招待URL: https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=2048&scope=bot"
    log_info ""
    log_info "🎉 Rakuten Monitor が正常にデプロイされました！"
}

# スクリプト実行
main "$@"