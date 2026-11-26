#!/usr/bin/env bash
# Step 9.2 nightly Postgres backup, keeps 7 days.
# Cron (crontab -e on the VM):  0 2 * * * cd /opt/finguard-ai && ./scripts/backup_db.sh >> /var/log/finguard-backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
mkdir -p backups
FILE="backups/finguard_$(date +%Y%m%d_%H%M%S).sql.gz"
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$FILE"
[ -s "$FILE" ] || { echo "backup is empty, failing"; rm -f "$FILE"; exit 1; }
find backups -name 'finguard_*.sql.gz' -mtime +7 -delete
echo "$(date -Is) backup ok: $FILE"
