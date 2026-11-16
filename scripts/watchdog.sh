#!/usr/bin/env bash
# Watchdog for the Ahmedabad Startup Jobs stack on this host.
#
# Keeps four things alive:
#   1. the FastAPI API
#   2. the Celery worker and beat scheduler
#   3. the public tunnel that Vercel proxies to
#   4. the Vercel deployment pointing at the current tunnel URL
#
# Each part is restarted independently, so a tunnel blip never takes the API or
# the ingestion workers down with it.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$HOME/.local/bin:/snap/bin:/usr/local/bin:/usr/bin:/bin"

API_FAILURES=0
TUNNEL_FAILURES=0
BACKOFF=0

check_api() {
  [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8000/health 2>/dev/null)" = "200" ]
}

check_tunnel() {
  local url
  url="$(cat /tmp/ahsj-tunnel-url 2>/dev/null)"
  [ -n "$url" ] || return 1
  [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 "$url/health" 2>/dev/null)" = "200" ]
}

check_worker() {
  ps -eo args | grep -q "[c]elery -A app.workers.*worker"
}

check_beat() {
  ps -eo args | grep -q "[c]elery -A app.workers.*beat"
}

while true; do
  if check_api; then
    API_FAILURES=0
  else
    API_FAILURES=$((API_FAILURES + 1))
    if [ "$API_FAILURES" -ge 2 ]; then
      echo "[watchdog] API unhealthy — restarting the API"
      "$ROOT/scripts/serve.sh" restart-api >/dev/null 2>&1
      API_FAILURES=0
      BACKOFF=15
    fi
  fi

  if check_worker; then
    :
  else
    echo "[watchdog] Celery worker missing — restarting the stack"
    "$ROOT/scripts/serve.sh" restart >/dev/null 2>&1
    BACKOFF=15
  fi

  if check_beat; then
    :
  else
    echo "[watchdog] Celery beat missing — restarting the scheduler"
    "$ROOT/scripts/serve.sh" restart-beat >/dev/null 2>&1
    BACKOFF=15
  fi

  if check_tunnel; then
    TUNNEL_FAILURES=0
  else
    TUNNEL_FAILURES=$((TUNNEL_FAILURES + 1))
    if [ "$TUNNEL_FAILURES" -ge 2 ]; then
      echo "[watchdog] tunnel unhealthy — restarting the tunnel only"
      "$ROOT/scripts/serve.sh" restart-tunnel >/dev/null 2>&1
      TUNNEL_FAILURES=0
      BACKOFF=15
    fi
  fi

  # Point the Vercel deployment at the current tunnel URL (no-op when unchanged).
  "$ROOT/scripts/sync_tunnel_to_vercel.sh" >/dev/null 2>&1

  sleep "$((BACKOFF > 0 ? BACKOFF : 60))"
  [ "$BACKOFF" -gt 0 ] && BACKOFF=0
done
