#!/usr/bin/env bash
# One-shot deployment: push to GitHub and deploy the frontend to Vercel.
#
# Assumes:
#   - `gh auth status` succeeds
#   - `vercel whoami` succeeds
#   - the backend is running and reachable through the tunnel
#     (scripts/serve.sh status)
#
# Usage: scripts/deploy_vercel.sh [--repo owner/name] [--skip-push]
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="${GITHUB_REPO:-}"
SKIP_PUSH=0
ENVIRONMENT_NAME="${VERCEL_ENV:-production}"

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --skip-push) SKIP_PUSH=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done

log() { printf '\033[36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

cd "$ROOT"

# --- 1. Preflight ------------------------------------------------------------
log "Checking prerequisites"
gh auth status >/dev/null 2>&1 || die "GitHub CLI is not authenticated (gh auth login)"
vercel whoami >/dev/null 2>&1 || die "Vercel CLI is not authenticated (vercel login)"

TUNNEL_URL="$(cat /tmp/ahsj-tunnel-url 2>/dev/null || true)"
[ -n "$TUNNEL_URL" ] || die "No tunnel URL found — run scripts/serve.sh start first"
curl -fsS "$TUNNEL_URL/health" >/dev/null 2>&1 || die "Tunnel is not responding ($TUNNEL_URL)"
log "Backend reachable at $TUNNEL_URL"

# --- 2. GitHub ---------------------------------------------------------------
if [ "$SKIP_PUSH" -eq 0 ]; then
  if [ -z "$REPO" ]; then
    REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)"
  fi
  if [ -z "$REPO" ]; then
    GH_USER="$(gh api user -q .login)"
    REPO="$GH_USER/ahmedabad-startup-jobs"
    log "Creating repository $REPO"
    gh repo create "$REPO" --public --description \
      "Real-time startup hiring intelligence for Ahmedabad, Gandhinagar and GIFT City" \
      --source=. --remote=origin || die "Could not create the GitHub repository"
  fi

  git remote remove origin 2>/dev/null || true
  git remote add origin "https://github.com/$REPO.git"
  log "Pushing to $REPO"
  git push -u origin HEAD || die "Could not push to GitHub"
fi

# --- 3. Vercel project -------------------------------------------------------
cd "$ROOT/frontend"

if [ ! -f .vercel/project.json ]; then
  log "Linking the Vercel project"
  vercel link --yes --project ahmedabad-startup-jobs || die "vercel link failed"
fi

# --- 4. Environment variables -------------------------------------------------
# The backend location is a runtime setting: changing it does not need a rebuild.
log "Setting environment variables"
vercel env add API_PROXY_TARGET "$TUNNEL_URL" --sensitive --yes "$ENVIRONMENT_NAME" \
  || vercel env rm API_PROXY_TARGET --yes "$ENVIRONMENT_NAME" \
  && vercel env add API_PROXY_TARGET "$TUNNEL_URL" --sensitive --yes "$ENVIRONMENT_NAME"

SITE_URL="$(vercel project ls 2>/dev/null | grep -oE 'https://[a-z0-9.-]+\.vercel\.app' | head -1 || true)"
[ -n "$SITE_URL" ] || SITE_URL="https://ahmedabad-startup-jobs.vercel.app"
vercel env add NEXT_PUBLIC_SITE_URL "$SITE_URL" --yes "$ENVIRONMENT_NAME" 2>/dev/null || true
log "API_PROXY_TARGET = $TUNNEL_URL"
log "NEXT_PUBLIC_SITE_URL = $SITE_URL"

# --- 5. Deploy ---------------------------------------------------------------
log "Deploying to Vercel ($ENVIRONMENT_NAME)"
vercel deploy --prod --yes || die "Deployment failed"

log "Done. Check the deployment with: vercel inspect"
