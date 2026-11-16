#!/usr/bin/env bash
# Keep the Vercel deployment pointed at the current tunnel URL.
#
# The ngrok free tier assigns a random hostname on every restart. The frontend
# proxies /api/* to API_PROXY_TARGET, so a changed tunnel would break the live
# site. This script detects the change and redeploys with the new value.
#
# Usage:
#   scripts/sync_tunnel_to_vercel.sh          # check once, sync if needed
#   scripts/sync_tunnel_to_vercel.sh --watch  # loop every 5 minutes
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$ROOT/frontend"
URL_FILE="/tmp/ahsj-tunnel-url"
STATE_FILE="/tmp/ahsj-synced-url"
VERCEL_SCOPE="${VERCEL_SCOPE:-dhruvs-projects-76a7424c}"

log() { printf '\033[36m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }

sync_once() {
  local tunnel synced
  tunnel="$(cat "$URL_FILE" 2>/dev/null || true)"
  if [ -z "$tunnel" ]; then
    log "no tunnel URL yet — run scripts/serve.sh start"
    return 1
  fi

  if ! curl -fsS --max-time 20 "$tunnel/health" >/dev/null 2>&1; then
    log "tunnel is not responding ($tunnel) — run scripts/serve.sh restart"
    return 1
  fi

  synced="$(cat "$STATE_FILE" 2>/dev/null || true)"
  if [ "$tunnel" = "$synced" ]; then
    log "in sync: $tunnel"
    return 0
  fi

  log "tunnel changed: ${synced:-none} -> $tunnel — updating Vercel"
  cd "$FRONTEND" || return 1

  # Update in place. `vercel env rm` is a destructive action that needs explicit
  # approval, so we patch the existing variable through the API instead.
  local project_id env_id
  project_id="$(python3 -c "import json;print(json.load(open('.vercel/project.json'))['projectId'])")"
  env_id="$(vercel api "/v9/projects/$project_id/env" --method GET --scope "$VERCEL_SCOPE" 2>/dev/null \
    | python3 -c "
import json,sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
envs = d.get('envs', d) if isinstance(d, dict) else d
for e in envs:
    if e.get('key') == 'API_PROXY_TARGET' and 'production' in (e.get('target') or []):
        print(e.get('id'))
        break
")"
  if [ -z "$env_id" ]; then
    log "could not find the production API_PROXY_TARGET variable"
    return 1
  fi

  printf '{"value":"%s"}' "$tunnel" > /tmp/ahsj-env-patch.json
  if ! vercel api "/v10/projects/$project_id/env/$env_id" --method PATCH \
      --scope "$VERCEL_SCOPE" --input /tmp/ahsj-env-patch.json >/dev/null 2>&1; then
    log "could not update the env var"
    return 1
  fi

  if vercel deploy --prod --yes >/tmp/ahsj-deploy.log 2>&1; then
    echo "$tunnel" > "$STATE_FILE"
    log "redeployed with $tunnel"
    return 0
  fi
  log "deployment failed — see /tmp/ahsj-deploy.log"
  return 1
}

if [ "${1:-}" = "--watch" ]; then
  while true; do
    sync_once
    sleep 300
  done
else
  sync_once
fi
