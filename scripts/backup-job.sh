#!/usr/bin/env bash
# Dijalankan oleh layanan `backup` (docker-compose.prod.yml) atau `make backup` (NFR-REL-002).
# Menghasilkan: db_<ts>.dump (pg_dump format custom), documents_<ts>.tar.gz, SHA256SUMS_<ts>
# lalu menghapus backup yang lebih tua dari BACKUP_RETENTION_DAYS.
set -euo pipefail
BACKUP_DIR="${BACKUP_DIR:-/backups}"
DOCUMENTS_DIR="${DOCUMENTS_DIR:-/documents}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"
cd "$BACKUP_DIR"

pg_dump --format=custom --no-owner --file "db_${TS}.dump"
if [ -d "$DOCUMENTS_DIR" ]; then
  tar -czf "documents_${TS}.tar.gz" -C "$DOCUMENTS_DIR" .
fi
sha256sum db_"${TS}".dump documents_"${TS}".tar.gz 2>/dev/null > "SHA256SUMS_${TS}" || true

find "$BACKUP_DIR" -maxdepth 1 -type f \( -name 'db_*.dump' -o -name 'documents_*.tar.gz' -o -name 'SHA256SUMS_*' \) \
  -mtime +"$RETENTION_DAYS" -delete
echo "[$(date -u +%FT%TZ)] backup selesai: db_${TS}.dump"
