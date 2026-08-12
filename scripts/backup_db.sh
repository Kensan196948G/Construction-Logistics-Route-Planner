#!/usr/bin/env bash
# Daily backup for Construction Logistics Route Planner.
# Supports SQLite (default) and PostgreSQL/PostGIS (pg_dump).
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups/daily"
# Optional override for drills/testing (defaults to the repo-local state.db).
DB_FILE="${DB_FILE:-${PROJECT_DIR}/state.db}"
RETENTION_DAYS=7
DATABASE_URL="${DATABASE_URL:-}"

mkdir -p "$BACKUP_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

if [[ "$DATABASE_URL" == postgresql* ]]; then
  CONN="${DATABASE_URL//+asyncpg/}"  # asyncpg URL -> psycopg/pg_dump URL
  BACKUP_FILE="${BACKUP_DIR}/pg_${TIMESTAMP}.dump.gz"
  pg_dump "$CONN" | gzip -c > "$BACKUP_FILE"
else
  if ! sqlite3 "$DB_FILE" "PRAGMA integrity_check;" | grep -q "^ok$"; then
    echo "[ERROR] SQLite integrity check failed; backup aborted" >&2
    exit 1
  fi
  BACKUP_FILE="${BACKUP_DIR}/state_${TIMESTAMP}.db.gz"
  sqlite3 "$DB_FILE" ".backup '${BACKUP_DIR}/state_${TIMESTAMP}.db'"
  gzip -f "${BACKUP_DIR}/state_${TIMESTAMP}.db"
fi

echo "[OK] Backup created: $BACKUP_FILE"
find "$BACKUP_DIR" \( -name '*.db.gz' -o -name '*.dump.gz' \) -mtime "+${RETENTION_DAYS}" -delete
echo "[OK] Cleaned up backups older than ${RETENTION_DAYS} days"
