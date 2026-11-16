#!/usr/bin/env bash
# Supervisor for the local backend stack: FastAPI + Celery + public tunnel.
#
# The frontend on Vercel proxies /api/* to this API through the tunnel, so both
# need to stay up. The script restarts whichever process dies and writes the
# current public URL to /tmp/ahsj-tunnel-url so it can be read by
# scripts/sync_tunnel_to_vercel.sh.
set -uo pipefail

ROOT="/home/dhruv2004/ahmedabad-startup-jobs/backend"
VENV="$ROOT/.venv/bin"
LOG_DIR="/tmp/ahsj-logs"
URL_FILE="/tmp/ahsj-tunnel-url"

mkdir -p "$LOG_DIR"

# The ngrok binary lives in a Snap install on some machines, which is not on
# the default PATH for systemd units. Resolve it explicitly.
find_ngrok() {
  if command -v ngrok >/dev/null 2>&1; then
    command -v ngrok
    return
  fi
  for candidate in /snap/bin/ngrok /usr/local/bin/ngrok /usr/bin/ngrok "$HOME/bin/ngrok"; do
    [ -x "$candidate" ] && { echo "$candidate"; return; }
  done
  echo "ngrok"
}

NGROK_BIN="$(find_ngrok)"

start_api() {
  cd "$ROOT" || exit 1
  setsid nohup "$VENV/uvicorn" app.main:app --host 127.0.0.1 --port 8000 \
    > "$LOG_DIR/api.log" 2>&1 < /dev/null &
}

start_worker() {
  cd "$ROOT" || exit 1
  setsid nohup "$VENV/celery" -A app.workers.celery_app.celery_app worker \
    --loglevel=info --concurrency=2 \
    > "$LOG_DIR/worker.log" 2>&1 < /dev/null &
}

start_beat() {
  cd "$ROOT" || exit 1
  setsid nohup "$VENV/celery" -A app.workers.celery_app.celery_app beat \
    --loglevel=info \
    > "$LOG_DIR/beat.log" 2>&1 < /dev/null &
}

start_tunnel() {
  rm -f "$LOG_DIR/ngrok.log"
  setsid nohup "$NGROK_BIN" http 8000 --log=stdout --log-format=json \
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
  echo "tunnel failed to start — see $LOG_DIR/ngrok.log" >&2
  return 1
}

kill_matching() {
  local pattern="$1"
  for p in $(ps -eo pid,args | grep -E "$pattern" | grep -v grep | awk '{print $1}'); do
    kill "$p" 2>/dev/null
  done
}

case "${1:-start}" in
  start)
    start_api
    start_worker
    start_beat
    sleep 6
    start_tunnel
    ;;
  restart)
    kill_matching "uvicorn app.main|ngrok http 8000|celery -A"
    sleep 3
    start_api
    start_worker
    start_beat
    sleep 6
    start_tunnel
    ;;
  restart-api)
    kill_matching "uvicorn app.main"
    sleep 2
    start_api
    ;;
  restart-tunnel)
    kill_matching "ngrok http 8000"
    sleep 2
    start_tunnel
    ;;
  stop)
    kill_matching "uvicorn app.main|ngrok http 8000|celery -A"
    echo "stopped"
    ;;
  status)
    url=$(cat "$URL_FILE" 2>/dev/null)
    workers=$(ps -eo args | grep -c "[c]elery -A app.workers" || true)
    echo "api:    $(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8000/health)"
    echo "tunnel: $(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "${url:-http://127.0.0.1:8000}/health")"
    echo "celery: $workers process(es)"
    echo "url:    ${url:-none}"
    ;;
  *)
    echo "usage: $0 {start|restart|restart-api|restart-tunnel|stop|status}" >&2
    exit 1
    ;;
esac
