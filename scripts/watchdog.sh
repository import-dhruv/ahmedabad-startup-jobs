#!/usr/bin/env bash
# Watchdog for the Ahmedabad Startup Jobs stack on this host.
#
# Keeps three things alive:
#   1. the FastAPI API
#   2. the public tunnel that Vercel proxies to
#   3. the Vercel deployment pointing at the current tunnel URL
#
# Install with:  scripts/install_watchdog.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"

TICK=0
while true; do
  TICK=$((TICK + 1))

  api_ok=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8000/health 2>/dev/null)
  if [ "$api_ok" != "200" ]; then
    echo "[watchdog] API unhealthy ($api_ok) — restarting"
    "$ROOT/scripts/serve.sh" restart >/dev/null 2>&1
    sleep 10
  fi

  tunnel="$(cat /tmp/ahsj-tunnel-url 2>/dev/null || true)"
  tunnel_ok=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "${tunnel:-http://127.0.0.1:8000}/health" 2>/dev/null)
  if [ "$tunnel_ok" != "200" ]; then
    echo "[watchdog] tunnel unhealthy ($tunnel_ok) — restarting"
    "$ROOT/scripts/serve.sh" restart >/dev/null 2>&1
    sleep 10
  fi

  # Sync the Vercel deployment with the current tunnel URL (no-ops when unchanged).
  "$ROOT/scripts/sync_tunnel_to_vercel.sh" >/dev/null 2>&1

  sleep 60
done
