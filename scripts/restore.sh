#!/usr/bin/env bash
# Pulihkan database (dan opsional dokumen) dari backup: 
#   ./scripts/restore.sh backups/db_<ts>.dump [backups/documents_<ts>.tar.gz]
# PERINGATAN: menimpa isi database saat ini. Setelah selesai, verifikasi:
#   rantai audit  -> GET /audit/verify (atau tombol "Verifikasi Rantai" di konsol Auditor)
set -euo pipefail
cd "$(dirname "$0")/.."
DUMP="${1:?Pemakaian: restore.sh <db.dump> [documents.tar.gz]}"
DOCS="${2:-}"
set -a; . ./.env; set +a
DC="${DOCKER_COMPOSE:-docker compose}"

read -r -p "Ini akan MENIMPA database ${POSTGRES_DB}. Lanjutkan? [ketik: ya] " ans
[ "$ans" = "ya" ] || { echo "Dibatalkan."; exit 1; }

$DC stop backend
# Trigger append-only menolak DELETE/TRUNCATE audit_logs, jadi database dibuat ulang dari nol.
$DC exec -T postgres psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${POSTGRES_DB}' AND pid<>pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS \"${POSTGRES_DB}\";" \
  -c "CREATE DATABASE \"${POSTGRES_DB}\";"
$DC exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error < "$DUMP"

if [ -n "$DOCS" ]; then
  mkdir -p data/documents
  tar -xzf "$DOCS" -C data/documents
fi
$DC start backend
echo "Restore selesai. Verifikasi rantai audit lewat konsol Auditor atau GET /audit/verify."
