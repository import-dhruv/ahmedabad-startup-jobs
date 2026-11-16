#!/usr/bin/env bash
# Install the watchdog as a systemd user service (with a cron fallback).
#
#   scripts/install_watchdog.sh
#
# The service keeps the API, the tunnel and the Vercel deployment in sync.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/ahmedabad-jobs-watchdog.service"

mkdir -p "$SERVICE_DIR"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Ahmedabad Startup Jobs watchdog (API + tunnel + Vercel sync)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$ROOT/scripts/watchdog.sh
Restart=always
RestartSec=10
Environment=PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=default.target
EOF

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload
  systemctl --user enable --now ahmedabad-jobs-watchdog.service
  echo "Installed: ahmedabad-jobs-watchdog.service"
  systemctl --user status ahmedabad-jobs-watchdog.service --no-pager | head -12
else
  echo "systemd unavailable — falling back to cron"
  ( crontab -l 2>/dev/null | grep -v "ahmedabad-jobs-watchdog"; \
    echo "* * * * * $ROOT/scripts/watchdog.sh >/dev/null 2>&1" ) | crontab -
  echo "Installed cron entry"
fi
