#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
WRANGLER_CONFIG="$PROJECT_ROOT/wrangler.toml"
PAGES_DIR="$PROJECT_ROOT/app/static"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { printf "${GREEN}[deploy]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[warn]${NC} %s\n" "$*"; }
err()  { printf "${RED}[error]${NC} %s\n" "$*"; }

check_deps() {
  if ! command -v npx &>/dev/null; then
    err "npx が見つかりません。Node.js をインストールしてください。"
    exit 1
  fi
}

check_env() {
  local missing=0
  for var in CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID; do
    if [ -z "${!var:-}" ]; then
      err "環境変数 $var が設定されていません。"
      missing=1
    fi
  done
  if [ "$missing" -eq 1 ]; then
    exit 1
  fi
}

check_assets() {
  if [ ! -d "$PAGES_DIR" ]; then
    err "Pages デプロイ対象ディレクトリが見つかりません: $PAGES_DIR"
    exit 1
  fi
  if [ ! -f "$PAGES_DIR/index.html" ]; then
    err "index.html が見つかりません: $PAGES_DIR/index.html"
    exit 1
  fi
}

deploy_pages() {
  local env="${1:-production}"
  log "Cloudflare Pages をデプロイ中 (環境: $env) ..."
  npx wrangler pages deploy "$PAGES_DIR" \
    --project-name="construction-logistics-route-planner" \
    --branch="$env" \
    --commit-dirty=true 2>&1
  log "Pages デプロイ完了"
}

deploy_worker() {
  local env="${1:-production}"
  log "Cloudflare Worker をデプロイ中 (環境: $env) ..."
  npx wrangler deploy \
    --config "$WRANGLER_CONFIG" \
    --env "$env" 2>&1
  log "Worker デプロイ完了"
}

main() {
  local env="${1:-production}"

  log "=== Construction Logistics Route Planner - Cloudflare デプロイ ==="
  log "環境: $env"

  check_deps
  check_env
  check_assets

  log ""
  log "バックエンドオリジン: ${BACKEND_ORIGIN:-http://localhost:8000}"

  deploy_pages "$env"

  log ""

  deploy_worker "$env"

  log ""
  log "=== デプロイ完了 ==="
  log "Pages URL:   https://construction-logistics-route-planner.pages.dev"
  log "Worker URL:  https://construction-logistics-route-planner.<account>.workers.dev"
  log ""
  log "ゾーン別 URL (設定後):"
  if [ "$env" = "production" ]; then
    log "  https://mirai-dx-platform.com/        (Pages)"
    log "  https://mirai-dx-platform.com/api/*   (Worker)"
  else
    log "  https://staging.mirai-dx-platform.com/        (Pages)"
    log "  https://staging.mirai-dx-platform.com/api/*   (Worker)"
  fi
}

main "$@"
