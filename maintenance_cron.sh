#!/bin/bash
# 楽天商品監視システム メンテナンス用cronスクリプト
#
# 使用方法:
# sudo ln -s /path/to/maintenance_cron.sh /etc/cron.weekly/rakuten-maintenance

set -euo pipefail

LOG_FILE="/var/log/rakuten_maintenance.log"
APP_DIR="/home/ubuntu/rakutenApp"

# ログ関数
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_message "Starting weekly maintenance"

# 1. システム更新チェック
log_message "Checking for system updates"
apt list --upgradable 2>/dev/null | wc -l | xargs -I {} log_message "Available updates: {}"

# 2. Python依存関係の更新チェック
log_message "Checking Python dependencies"
cd "$APP_DIR"
pip list --outdated --format=json 2>/dev/null | python3 -c "
import json, sys
try:
    packages = json.load(sys.stdin)
    if packages:
        print(f'Outdated packages: {len(packages)}')
        for pkg in packages[:5]:  # Show first 5
            print(f'  - {pkg[\"name\"]}: {pkg[\"version\"]} -> {pkg[\"latest_version\"]}')
    else:
        print('All packages are up to date')
except:
    print('Could not check package updates')
" | tee -a "$LOG_FILE"

# 3. ログファイルのクリーンアップ
log_message "Cleaning up old logs"
find "$APP_DIR" -name "*.log.*" -mtime +30 -type f -exec rm -f {} \; 2>/dev/null || true
find /var/log -name "rakuten_*.log.*" -mtime +30 -type f -exec rm -f {} \; 2>/dev/null || true

# 4. データベースの最適化とチェック
if [ -f "$APP_DIR/rakuten_monitor.db" ]; then
    log_message "Optimizing database"
    sqlite3 "$APP_DIR/rakuten_monitor.db" "PRAGMA optimize; VACUUM;"

    log_message "Checking database integrity"
    if sqlite3 "$APP_DIR/rakuten_monitor.db" "PRAGMA integrity_check;" | grep -q "ok"; then
        log_message "Database integrity: OK"
    else
        log_message "WARNING: Database integrity check failed"
    fi

    # データベースサイズ記録
    DB_SIZE=$(ls -lh "$APP_DIR/rakuten_monitor.db" | awk '{print $5}')
    log_message "Database size: $DB_SIZE"
fi

# 5. ディスク使用量チェック
DISK_USAGE=$(df -h "$APP_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')
log_message "Disk usage: ${DISK_USAGE}%"

if [ "$DISK_USAGE" -gt 80 ]; then
    log_message "WARNING: High disk usage detected"
fi

# 6. サービス状態チェック
log_message "Checking service status"
if systemctl is-active --quiet rakuten-monitor.timer; then
    log_message "Service status: Active"
    NEXT_RUN=$(systemctl list-timers | grep rakuten-monitor | awk '{print $1, $2}')
    log_message "Next run: $NEXT_RUN"
else
    log_message "WARNING: Service is not active"
fi

# 7. ネットワーク疎通確認
log_message "Testing network connectivity"
if curl -s --connect-timeout 10 "https://item.rakuten.co.jp/auc-p-entamestore/c/0000000174/?s=4" > /dev/null; then
    log_message "Rakuten site: Accessible"
else
    log_message "WARNING: Cannot access Rakuten site"
fi

# 8. Prometheusメトリクス確認
if curl -s http://localhost:8000/metrics > /dev/null 2>&1; then
    log_message "Prometheus metrics: Available"

    # 最後の実行状態を確認
    LAST_STATUS=$(curl -s http://localhost:8000/metrics | grep "rakuten_last_run_status" | tail -1 | awk '{print $2}')
    if [ "${LAST_STATUS:-0}" = "1" ]; then
        log_message "Last monitoring run: Success"
    else
        log_message "WARNING: Last monitoring run failed"
    fi
else
    log_message "WARNING: Prometheus metrics not available"
fi

# 9. セキュリティチェック
log_message "Running security checks"

# ファイル権限チェック
if [ -f ".env" ] && [ "$(stat -c %a .env)" != "600" ]; then
    log_message "WARNING: .env file permissions are not secure"
fi

if [ -f "/etc/rakuten_monitor.env" ] && [ "$(stat -c %a /etc/rakuten_monitor.env)" != "600" ]; then
    log_message "WARNING: /etc/rakuten_monitor.env permissions are not secure"
fi

# 10. メモリ使用量チェック
MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
log_message "Memory usage: ${MEMORY_USAGE}%"

# プロセス確認
PYTHON_PROCESSES=$(pgrep -f "python.*monitor.py" | wc -l)
if [ "$PYTHON_PROCESSES" -gt 1 ]; then
    log_message "WARNING: Multiple monitor processes detected ($PYTHON_PROCESSES)"
fi

# 11. 統計情報の収集
if [ -f "$APP_DIR/rakuten_monitor.db" ]; then
    log_message "Collecting statistics"

    # 商品数
    ITEM_COUNT=$(sqlite3 "$APP_DIR/rakuten_monitor.db" "SELECT COUNT(*) FROM items;" 2>/dev/null || echo "0")
    log_message "Total items: $ITEM_COUNT"

    # 今週の変更数
    WEEKLY_CHANGES=$(sqlite3 "$APP_DIR/rakuten_monitor.db" "SELECT COUNT(*) FROM changes WHERE occurred_at > datetime('now', '-7 days');" 2>/dev/null || echo "0")
    log_message "Changes this week: $WEEKLY_CHANGES"

    # 実行回数（今週）
    WEEKLY_RUNS=$(sqlite3 "$APP_DIR/rakuten_monitor.db" "SELECT COUNT(*) FROM runs WHERE fetched_at > datetime('now', '-7 days');" 2>/dev/null || echo "0")
    log_message "Runs this week: $WEEKLY_RUNS"
fi

# 12. 自動修復の実行
log_message "Running automatic repairs"

# ログファイル権限の修正
chmod 644 "$APP_DIR"/*.log 2>/dev/null || true
chmod 600 "$APP_DIR/.env" 2>/dev/null || true

# 一時ファイルのクリーンアップ
find "$APP_DIR" -name "*.tmp" -type f -mtime +1 -delete 2>/dev/null || true
find "$APP_DIR" -name "*.temp" -type f -mtime +1 -delete 2>/dev/null || true

# __pycache__のクリーンアップ
find "$APP_DIR" -name "__pycache__" -type d -exec rm -rf {} \; 2>/dev/null || true

log_message "Weekly maintenance completed"

# 13. 結果の要約とDiscord通知（オプション）
if [ -n "${DISCORD_WEBHOOK_URL:-}" ] && [ "$DISK_USAGE" -gt 85 ] || [ "${LAST_STATUS:-0}" != "1" ]; then
    curl -H "Content-Type: application/json" \
         -X POST \
         -d "{
           \"embeds\": [{
             \"title\": \"⚠️ Maintenance Alert\",
             \"description\": \"Weekly maintenance found issues that need attention\",
             \"color\": 16776960,
             \"fields\": [
               {\"name\": \"Disk Usage\", \"value\": \"${DISK_USAGE}%\", \"inline\": true},
               {\"name\": \"Last Run Status\", \"value\": \"${LAST_STATUS:-Unknown}\", \"inline\": true},
               {\"name\": \"Date\", \"value\": \"$(date '+%Y-%m-%d')\", \"inline\": true}
             ]
           }]
         }" \
         "$DISCORD_WEBHOOK_URL" 2>/dev/null || log_message "Failed to send Discord notification"
fi

exit 0
