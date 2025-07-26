#!/bin/bash
# systemd setup script for Rakuten Monitor

# Copy service files to systemd directory
sudo cp rakuten-monitor.service /etc/systemd/system/
sudo cp rakuten-monitor.timer /etc/systemd/system/

# Create environment file
sudo cp .env /etc/rakuten_monitor.env
sudo chmod 600 /etc/rakuten_monitor.env

# Reload systemd and enable timer
sudo systemctl daemon-reload
sudo systemctl enable --now rakuten-monitor.timer

# Show status
echo "=== Timer Status ==="
sudo systemctl status rakuten-monitor.timer

echo "=== Next Run Times ==="
sudo systemctl list-timers | grep rakuten