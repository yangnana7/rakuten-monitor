#!/bin/bash

# Rakuten Monitor systemd service installation script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/rakuten-monitor.service"
TIMER_FILE="$SCRIPT_DIR/rakuten-monitor.timer"
SYSTEMD_DIR="/etc/systemd/system"

echo "=== Rakuten Monitor systemd Service Installation ==="
echo "Script directory: $SCRIPT_DIR"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    echo "❌ Please do not run this script as root. Use sudo when prompted."
    exit 1
fi

# Check if service files exist
if [[ ! -f "$SERVICE_FILE" ]]; then
    echo "❌ Service file not found: $SERVICE_FILE"
    exit 1
fi

if [[ ! -f "$TIMER_FILE" ]]; then
    echo "❌ Timer file not found: $TIMER_FILE"
    exit 1
fi

echo "✅ Service files found"

# Stop and disable existing services if they exist
echo "🔄 Stopping existing services if running..."
sudo systemctl stop rakuten-monitor.timer 2>/dev/null || true
sudo systemctl stop rakuten-monitor.service 2>/dev/null || true
sudo systemctl disable rakuten-monitor.timer 2>/dev/null || true

# Copy service files to systemd directory
echo "📁 Installing service files..."
sudo cp "$SERVICE_FILE" "$SYSTEMD_DIR/"
sudo cp "$TIMER_FILE" "$SYSTEMD_DIR/"

# Set correct permissions
sudo chmod 644 "$SYSTEMD_DIR/rakuten-monitor.service"
sudo chmod 644 "$SYSTEMD_DIR/rakuten-monitor.timer"

echo "✅ Service files installed"

# Reload systemd daemon
echo "🔄 Reloading systemd daemon..."
sudo systemctl daemon-reload

# Enable and start the timer
echo "🚀 Enabling and starting rakuten-monitor.timer..."
sudo systemctl enable rakuten-monitor.timer
sudo systemctl start rakuten-monitor.timer

# Show status
echo ""
echo "=== Service Status ==="
sudo systemctl status rakuten-monitor.timer --no-pager -l
echo ""
echo "=== Timer Schedule ==="
sudo systemctl list-timers rakuten-monitor.timer --no-pager
echo ""
echo "=== Recent Logs ==="
sudo journalctl -u rakuten-monitor.service -n 5 --no-pager || echo "No logs yet (first run pending)"

echo ""
echo "✅ Installation completed successfully!"
echo ""
echo "📋 Useful commands:"
echo "  Check timer status:    sudo systemctl status rakuten-monitor.timer"
echo "  Check service logs:    sudo journalctl -u rakuten-monitor.service -f"
echo "  Stop monitoring:       sudo systemctl stop rakuten-monitor.timer"
echo "  Start monitoring:      sudo systemctl start rakuten-monitor.timer"
echo "  Restart monitoring:    sudo systemctl restart rakuten-monitor.timer"
echo "  Manual run:            sudo systemctl start rakuten-monitor.service"
echo ""
echo "🕐 The monitor will run every 15 minutes from 09:00 to 22:00"