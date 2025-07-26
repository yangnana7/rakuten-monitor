#!/bin/bash
# 楽天商品監視システム セキュリティセットアップスクリプト

set -euo pipefail

# 色付きメッセージ関数
print_info() {
    echo -e "\033[1;34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[1;32m[SUCCESS]\033[0m $1"
}

print_warning() {
    echo -e "\033[1;33m[WARNING]\033[0m $1"
}

print_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1"
}

print_info "楽天商品監視システム セキュリティセットアップを開始します"

# 1. ファイル権限の設定
print_info "ファイル権限を設定中..."

# 環境設定ファイルの権限（600: オーナーのみ読み書き可能）
if [ -f "/etc/rakuten_monitor.env" ]; then
    sudo chmod 600 /etc/rakuten_monitor.env
    sudo chown root:root /etc/rakuten_monitor.env
    print_success "Set secure permissions for /etc/rakuten_monitor.env"
fi

if [ -f ".env" ]; then
    chmod 600 .env
    print_success "Set secure permissions for .env"
fi

# データベースファイルの権限（660: オーナーとグループが読み書き可能）
if [ -f "rakuten_monitor.db" ]; then
    chmod 660 rakuten_monitor.db
    print_success "Set secure permissions for database file"
fi

# ログファイルの権限（644: オーナー読み書き、その他読み込みのみ）
chmod 644 *.log 2>/dev/null || true
print_success "Set permissions for log files"

# 2. UFW ファイアウォール設定
print_info "ファイアウォール設定を確認中..."

if command -v ufw > /dev/null; then
    # Prometheusメトリクスポート（8000）を内部ネットワークのみに制限
    sudo ufw allow from 192.168.0.0/16 to any port 8000 comment 'Prometheus metrics - internal network only'
    sudo ufw allow from 10.0.0.0/8 to any port 8000 comment 'Prometheus metrics - internal network only'
    sudo ufw allow from 172.16.0.0/12 to any port 8000 comment 'Prometheus metrics - internal network only'
    
    # ローカルホストからのアクセスは常に許可
    sudo ufw allow from 127.0.0.1 to any port 8000 comment 'Prometheus metrics - localhost'
    
    # 外部からの8000ポートへのアクセスを拒否
    sudo ufw deny 8000 comment 'Block external access to Prometheus metrics'
    
    print_success "Firewall rules configured for Prometheus metrics"
else
    print_warning "UFW not available. Please configure firewall manually."
fi

# 3. システムユーザーとグループの設定
print_info "システムユーザー設定を確認中..."

# 専用ユーザーの作成（存在しない場合）
if ! id "rakuten-monitor" &>/dev/null; then
    sudo useradd -r -s /bin/false -d /home/ubuntu/rakutenApp rakuten-monitor
    print_success "Created dedicated user: rakuten-monitor"
else
    print_info "User rakuten-monitor already exists"
fi

# ファイルオーナーシップの設定
sudo chown -R ubuntu:rakuten-monitor /home/ubuntu/rakutenApp 2>/dev/null || true
print_success "Set file ownership"

# 4. システムサービスのセキュリティ強化
print_info "systemd サービスのセキュリティを強化中..."

# セキュリティ強化版のサービスファイルを作成
cat << 'EOF' | sudo tee /etc/systemd/system/rakuten-monitor-secure.service > /dev/null
[Unit]
Description=Rakuten Shop Watcher (Security Hardened)
After=network-online.target

[Service]
Type=oneshot
User=ubuntu
Group=rakuten-monitor
EnvironmentFile=/etc/rakuten_monitor.env
WorkingDirectory=/home/ubuntu/rakutenApp
ExecStart=/home/ubuntu/.venv/bin/python monitor.py
StandardOutput=append:/var/log/rakuten_monitor.log
StandardError=append:/var/log/rakuten_monitor.err

# セキュリティ設定
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/home/ubuntu/rakutenApp /var/log
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictRealtime=yes
RestrictSUIDSGID=yes
RemoveIPC=yes
RestrictNamespaces=yes

# ネットワーク制限
IPAddressDeny=any
IPAddressAllow=localhost
IPAddressAllow=127.0.0.1/8
IPAddressAllow=item.rakuten.co.jp
IPAddressAllow=discord.com

# リソース制限
Nice=5
MemoryMax=512M
CPUQuota=50%

# タイムアウト設定
TimeoutStartSec=60
TimeoutStopSec=30
EOF

print_success "Created security-hardened service file"

# 5. ログファイルのセキュリティ設定
print_info "ログファイルのセキュリティを設定中..."

# ログディレクトリの権限設定
sudo mkdir -p /var/log/rakuten_monitor
sudo chown ubuntu:rakuten-monitor /var/log/rakuten_monitor
sudo chmod 750 /var/log/rakuten_monitor

# logrotate設定の強化
cat << 'EOF' | sudo tee /etc/logrotate.d/rakuten_monitor_secure > /dev/null
/var/log/rakuten_monitor/*.log /home/ubuntu/rakutenApp/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 640 ubuntu rakuten-monitor
    sharedscripts
    postrotate
        # ログローテーション後にシステムに通知
        if systemctl is-active --quiet rakuten-monitor.timer; then
            logger "Rakuten monitor logs rotated"
        fi
    endscript
}
EOF

print_success "Enhanced log rotation configuration"

# 6. 機密情報のスキャン
print_info "機密情報のスキャンを実行中..."

# 設定ファイル内の潜在的な機密情報をチェック
scan_secrets() {
    local file="$1"
    if [ -f "$file" ]; then
        # APIキー、パスワード、トークンなどの検出
        if grep -i -E "(password|secret|key|token|webhook)" "$file" | grep -v "^#" | grep -q "=.*[a-zA-Z0-9]{20,}"; then
            print_warning "Potential secrets found in $file"
            return 1
        fi
    fi
    return 0
}

# メインファイルのスキャン
for file in .env rakuten_monitor.env /etc/rakuten_monitor.env; do
    if [ -f "$file" ]; then
        if scan_secrets "$file"; then
            print_success "No secrets exposed in $file"
        fi
    fi
done

# 7. ネットワークセキュリティチェック
print_info "ネットワークセキュリティをチェック中..."

# 開いているポートの確認
open_ports=$(ss -tulpn | grep :8000 || true)
if [ -n "$open_ports" ]; then
    print_info "Prometheus metrics port 8000 is open:"
    echo "$open_ports"
else
    print_info "Prometheus metrics port 8000 is not currently listening"
fi

# 8. 自動セキュリティ更新の設定
print_info "自動セキュリティ更新を設定中..."

if command -v unattended-upgrades > /dev/null; then
    # 自動セキュリティ更新を有効化
    sudo dpkg-reconfigure -plow unattended-upgrades 2>/dev/null || true
    print_success "Enabled automatic security updates"
else
    print_warning "unattended-upgrades not available. Install it for automatic security updates."
fi

# 9. fail2ban の設定（SSH保護）
print_info "fail2ban設定を確認中..."

if command -v fail2ban-client > /dev/null; then
    sudo systemctl enable fail2ban
    sudo systemctl start fail2ban
    print_success "fail2ban enabled for SSH protection"
else
    print_warning "fail2ban not installed. Consider installing it for SSH protection."
fi

# 10. セキュリティ監査ログの設定
print_info "セキュリティ監査ログを設定中..."

# systemdサービスの設定をリロード
sudo systemctl daemon-reload

# セキュリティ強化版サービスを使用するかの選択
print_info "セキュリティ強化版サービスファイルが作成されました:"
echo "  - 標準版: rakuten-monitor.service"
echo "  - セキュリティ強化版: rakuten-monitor-secure.service"
echo ""
print_info "セキュリティ強化版を使用する場合は以下を実行してください:"
echo "  sudo systemctl disable rakuten-monitor.timer"
echo "  sudo systemctl enable rakuten-monitor-secure.timer"

# 11. セキュリティチェックスクリプトの作成
print_info "定期セキュリティチェックスクリプトを作成中..."

cat << 'EOF' > security_check.sh
#!/bin/bash
# 定期セキュリティチェックスクリプト

echo "=== Rakuten Monitor Security Check ==="
echo "Date: $(date)"
echo

# ファイル権限チェック
echo "File Permissions:"
ls -la .env rakuten_monitor.db *.log 2>/dev/null | head -10

echo
echo "Service Status:"
systemctl is-active rakuten-monitor.timer 2>/dev/null || echo "Service not running"

echo
echo "Network Connections:"
ss -tulpn | grep :8000 || echo "Port 8000 not listening"

echo
echo "Recent Failed Logins:"
lastb | head -5 2>/dev/null || echo "No failed logins recorded"

echo
echo "Disk Usage:"
df -h . | tail -1

echo "=== End Security Check ==="
EOF

chmod +x security_check.sh
print_success "Created security check script: security_check.sh"

print_success "セキュリティセットアップが完了しました！"
print_info "定期的に ./security_check.sh を実行してセキュリティ状態を確認してください"