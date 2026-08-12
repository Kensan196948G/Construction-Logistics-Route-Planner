#!/usr/bin/env bash
# Restore a backup for Construction Logistics Route Planner.
# Usage: restore_db.sh <backup-file>
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup-file>" >&2
  exit 2
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Optional override for drills/testing (defaults to the repo-local state.db).
DB_FILE="${DB_FILE:-${PROJECT_DIR}/state.db}"
DATABASE_URL="${DATABASE_URL:-}"
BACKUP_FILE="$1"

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "[ERROR] Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

if [[ "$DATABASE_URL" == postgresql* ]]; then
  CONN="${DATABASE_URL//+asyncpg/}"
  gunzip -c "$BACKUP_FILE" | pg_restore --clean --if-exists -d "$CONN"
  echo "[OK] PostgreSQL restored from $BACKUP_FILE"
else
  gunzip -c "$BACKUP_FILE" > "${DB_FILE}.restore"
  sqlite3 "${DB_FILE}.restore" "PRAGMA integrity_check;" | grep -q "^ok$"
  mv "${DB_FILE}.restore" "$DB_FILE"
  echo "[OK] SQLite restored to $DB_FILE"
fi
