#!/usr/bin/env bash
# Membuat sertifikat self-signed untuk uji profil produksi (nginx & PostgreSQL).
# Di produksi, ganti server.crt / server.key dengan sertifikat dari CA resmi.
set -euo pipefail
cd "$(dirname "$0")"
HOST="${1:-localhost}"
if [ -f server.crt ] && [ -f server.key ]; then
  echo "Sertifikat sudah ada di infra/certs (hapus dulu untuk membuat ulang)."
  exit 0
fi
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout server.key -out server.crt \
  -subj "/CN=${HOST}" \
  -addext "subjectAltName=DNS:${HOST},DNS:localhost,DNS:postgres,IP:127.0.0.1"
chmod 600 server.key
echo "Sertifikat dibuat: infra/certs/server.crt, infra/certs/server.key (CN=${HOST})"
