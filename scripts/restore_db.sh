#!/usr/bin/env bash
# CP-9.2 restore drill:  ./scripts/restore_db.sh backups/finguard_YYYYMMDD_HHMMSS.sql.gz
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
FILE="${1:?usage: restore_db.sh <backup.sql.gz>}"
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $POSTGRES_DB;"
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $POSTGRES_DB;"
gunzip -c "$FILE" | docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
echo "restored from $FILE"
