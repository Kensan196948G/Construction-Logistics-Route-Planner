#!/usr/bin/env bash
# Health + basic metrics monitor for Construction Logistics Route Planner.
# Exit code 1 when health checks fail (for cron + alerting).
set -euo pipefail

BASE_URL="${MONITOR_BASE_URL:-http://127.0.0.1:18017}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_FILE="${PROJECT_DIR}/state.db"

status="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$BASE_URL/api/health" || true)"
if [[ "$status" != "200" ]]; then
  echo "[CRITICAL] /api/health returned $status" >&2
  exit 1
fi

if [[ -f "$DB_FILE" ]]; then
  size="$(stat -c%s "$DB_FILE")"
  if [[ "$size" -gt 1073741824 ]]; then
    echo "[CRITICAL] state.db size ${size} bytes exceeds 1GB" >&2
    exit 1
  fi
fi

echo "[OK] health=$status db_size=${size:-n/a}"
