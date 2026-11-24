#!/usr/bin/env bash
# Backup manual dari host (NFR-REL-002): ./scripts/backup.sh  atau  make backup
# Hasil di ./backups: db_<ts>.dump (pg_dump format custom) + documents_<ts>.tar.gz + SHA256SUMS_<ts>
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
DC="${DOCKER_COMPOSE:-docker compose}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p backups
$DC exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner > "backups/db_${TS}.dump"
if [ -d data/documents ]; then
  tar -czf "backups/documents_${TS}.tar.gz" -C data/documents .
fi
( cd backups && sha256sum "db_${TS}.dump" documents_"${TS}".tar.gz 2>/dev/null > "SHA256SUMS_${TS}" || true )
ls -lh backups | tail -5
