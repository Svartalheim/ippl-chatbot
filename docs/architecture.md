# Arsitektur & Pemenuhan Kebutuhan Infrastruktur

Diagram: `docs/diagrams/deployment.puml` (halaman 1: pengembangan, halaman 2: target produksi).

## Profil yang tersedia

| Profil | Perintah | Untuk |
|---|---|---|
| Pengembangan | `make up` | Hot reload, semua port terbuka ke host, HTTP |
| Produksi / staging | `make up-prod` (`docker-compose.yml` + `docker-compose.prod.yml`) | TLS 1.3, Postgres SSL, backend multi-worker, backup otomatis, hanya port 80/443 terbuka |

## Pemetaan NFR infrastruktur

| Kebutuhan | Cara dipenuhi | Status |
|---|---|---|
| §2.4.1 HTTPS / TLS 1.3 | nginx (`infra/nginx/nginx.conf`) `ssl_protocols TLSv1.3`, HSTS, redirect 80→443 | Terimplementasi (profil prod) |
| NFR-SEC-009 Koneksi orkestrator ↔ vector DB terautentikasi & terenkripsi | Postgres `ssl=on`; backend `?ssl=require`; Keycloak `sslmode=require`; Postgres tidak dipublikasikan | Terimplementasi (profil prod) |
| NFR-SEC-007 Enkripsi at rest AES-256 | Diserahkan ke lapisan penyimpanan: volume/disk terenkripsi (LUKS / enkripsi disk cloud, AES-256) atau managed PostgreSQL dengan enkripsi at rest. Enkripsi kolom aplikasi tidak dipakai karena vektor `embedding` harus dapat dibandingkan oleh pgvector; kolom `content` dapat dienkripsi pgcrypto tetapi memutus pratinjau & pencarian, sehingga tidak dipilih. | Kebijakan penerapan (dokumentasi) |
| NFR-SEC-008 CMEK | Managed PostgreSQL / disk dengan kunci dari KMS perusahaan (AWS KMS, Azure Key Vault, Cloud KMS) | Kebijakan penerapan (dokumentasi) |
| NFR-SEC-014 Embedding dilindungi setara teks | Embedding berada di tabel & volume yang sama dengan teks, mewarisi enkripsi disk dan filter klasifikasi per chunk | Terpenuhi |
| NFR-REL-001 Uptime 99,9% | `restart: unless-stopped` + healthcheck backend; target produksi: ≥2 replika backend di belakang load balancer, managed Postgres HA | Sebagian (perlu infrastruktur cloud) |
| NFR-REL-002 Backup & restore otomatis | Layanan `backup` (pg_dump harian + arsip dokumen + SHA256SUMS, rotasi `BACKUP_RETENTION_DAYS`); `make backup`, `make restore` | Terimplementasi |
| NFR-SEC-018 Retensi log audit | `AUDIT_RETENTION_DAYS` + `make audit-retention` (arsip JSONL bertanda SHA-256, entri `AUDIT_ARCHIVE` sebagai jangkar rantai) | Terimplementasi |
| NFR-SCL-001 10× dokumen | Indeks HNSW `vector_cosine_ops` pada `document_chunks.embedding`; filter klasifikasi berindeks | Terpenuhi secara desain; perlu uji beban data |
| NFR-SCL-002 5× pengguna | Backend stateless, `--workers`, kunci advisory saat startup agar migrasi/seed aman untuk banyak worker/replika; file dokumen di volume bersama | Terimplementasi; target prod: object storage |
| NFR-PERF-001/002 | `scripts/load_test_4c.py` (`make test-perf`) | Perlu dijalankan & dicatat (VER-03) |

## Catatan operasional
- Sertifikat: `make certs` membuat sertifikat self-signed untuk uji; di produksi ganti `infra/certs/server.crt|key` dengan sertifikat CA.
- Realm Keycloak pengembangan memakai `sslRequired: none` agar akses HTTP via IP jaringan internal tetap berfungsi. Di produksi set `sslRequired: external` melalui konsol admin Keycloak.
- Keycloak tidak perlu dibuka ke publik: login berjalan melalui backend (`/auth/login`), dan backend memvalidasi issuer internal maupun publik.
- Restore menimpa database; setelah restore jalankan verifikasi rantai audit dari konsol Auditor.
