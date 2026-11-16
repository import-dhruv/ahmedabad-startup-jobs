#!/usr/bin/env bash
# Supervisor for the local backend stack: FastAPI + the public tunnel.
#
# The frontend on Vercel proxies /api/* to this API through the tunnel, so both
# need to stay up. The script restarts whichever process dies and writes the
# current public URL to /tmp/ahsj-tunnel-url so it can be read by scripts.
set -uo pipefail

ROOT="/home/dhruv2004/ahmedabad-startup-jobs/backend"
VENV="$ROOT/.venv/bin"
LOG_DIR="/tmp/ahsj-logs"
URL_FILE="/tmp/ahsj-tunnel-url"

mkdir -p "$LOG_DIR"

start_api() {
  cd "$ROOT" || exit 1
  setsid nohup "$VENV/uvicorn" app.main:app --host 127.0.0.1 --port 8000 \
    > "$LOG_DIR/api.log" 2>&1 < /dev/null &
}

start_tunnel() {
  rm -f "$LOG_DIR/ngrok.log"
  setsid nohup ngrok http 8000 --log=stdout --log-format=json \
    > "$LOG_DIR/ngrok.log" 2>&1 < /dev/null &
  # Wait for the tunnel URL to appear.
  for _ in $(seq 1 30); do
    sleep 1
    url=$(grep -oE '"url":"https://[^"]+"' "$LOG_DIR/ngrok.log" 2>/dev/null | head -1 | sed 's/"url":"//;s/"//')
    if [ -n "$url" ]; then
      echo "$url" > "$URL_FILE"
      echo "tunnel: $url"
      return 0
    fi
  done
  echo "tunnel failed to start" >&2
}

case "${1:-start}" in
  start)
    start_api
    sleep 6
    start_tunnel
    ;;
  restart)
    for p in $(ps -eo pid,args | grep -E "uvicorn app.main|ngrok http 8000" | grep -v grep | awk '{print $1}'); do
      kill "$p" 2>/dev/null
    done
    sleep 3
    start_api
    sleep 6
    start_tunnel
    ;;
  stop)
    for p in $(ps -eo pid,args | grep -E "uvicorn app.main|ngrok http 8000" | grep -v grep | awk '{print $1}'); do
      kill "$p" 2>/dev/null
    done
    echo "stopped"
    ;;
  status)
    url=$(cat "$URL_FILE" 2>/dev/null)
    echo "api:    $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health)"
    echo "tunnel: $(curl -s -o /dev/null -w '%{http_code}' "${url:-http://127.0.0.1:8000}/health")"
    echo "url:    ${url:-none}"
    ;;
  *)
    echo "usage: $0 {start|restart|stop|status}" >&2
    exit 1
    ;;
esac
