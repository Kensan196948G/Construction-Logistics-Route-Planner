#!/usr/bin/env bash
# Health + basic metrics monitor for Construction Logistics Route Planner.
# Exit code 1 when health checks fail (for cron + alerting).
set -euo pipefail

BASE_URL="${MONITOR_BASE_URL:-http://127.0.0.1:18017}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_FILE="${PROJECT_DIR}/state.db"

health_json="$(curl -s --max-time 5 "$BASE_URL/api/health" || true)"
status="$(printf '%s' "$health_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status","error"))' 2>/dev/null || echo error)"
db_status="$(printf '%s' "$health_json" | python3 -c 'import json,sys; print((json.load(sys.stdin).get("db") or {}).get("status","error"))' 2>/dev/null || echo error)"
if [[ "$status" != "ok" ]]; then
  echo "[CRITICAL] /api/health returned status=$status" >&2
  exit 1
fi
if [[ "$db_status" != "ok" ]]; then
  echo "[CRITICAL] database check returned db.status=$db_status" >&2
  exit 1
fi

if [[ -f "$DB_FILE" ]]; then
  size="$(stat -c%s "$DB_FILE")"
  if [[ "$size" -gt 1073741824 ]]; then
    echo "[CRITICAL] state.db size ${size} bytes exceeds 1GB" >&2
    exit 1
  fi
fi

echo "[OK] health=$status db.status=$db_status db_size=${size:-n/a}"
