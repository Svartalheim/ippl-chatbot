# Tinjauan Keamanan (VER-02)

Lingkup: `backend/app` dan konfigurasi Docker/Keycloak pada commit saat ini, dibandingkan dengan SKPL §2.5 dan NFR-SEC-001..018.

| # | Temuan | Dampak | Status |
|---|---|---|---|
| S1 | `POST /chat/messages/{id}/feedback` tidak memeriksa kepemilikan pesan (IDOR): pengguna dapat memberi/menimpa feedback pada pesan orang lain. | Integritas data feedback | **Diperbaiki**: hanya jawaban asisten di sesi milik pengguna (404 selain itu). |
| S2 | Nama file unggahan dipakai langsung di path `data/documents/{id}_{filename}`; nama berisi `../` berpotensi path traversal. | Penulisan file di luar folder | **Diperbaiki**: `sanitize_filename` + validasi ekstensi & tanda tangan file. |
| S3 | Log audit kueri hanya 40 karakter pertama dan tanpa ID chunk (NFR-SEC-015/016). | Audit tidak lengkap | **Diperbaiki**: teks lengkap (PII disamarkan, maks `AUDIT_QUERY_MAX_CHARS`) + `chunk_diambil` + `dokumen_dikutip`. |
| S4 | Teks kueri mentah ditulis ke log aplikasi (`logger.warning(... {query})`). | PII di log (NFR-SEC-010) | **Diperbaiki**: `redact_pii` di semua log aplikasi & audit. |
| S5 | `sync_user_to_db` menimpa `users.role_id` dari klaim Keycloak pada setiap permintaan, dan RBAC memakai peran dari JWT. Perubahan "Ubah Peran Pengguna" di konsol Admin tidak bertahan/berpengaruh bila berbeda dari Keycloak. | Admin mengira peran berubah padahal tidak (FR-ADMIN-001) | **Terbuka — perlu keputusan tim**: (a) jadikan Keycloak sumber kebenaran dan ubah aksi Admin agar memanggil Admin API Keycloak, atau (b) jadikan DB sumber kebenaran dan hentikan penimpaan role di `sync_user_to_db`. SKPL §1.2 (penetapan grup oleh IdP) mendukung opsi (a). |
| S6 | Deteksi `QUERY_DENIED` menjalankan pencarian global tanpa filter (top-1) dan memberi tahu nama klasifikasi dokumen terkait. Isi chunk tidak pernah dikirim ke LLM. | Kebocoran metadata minimal (keberadaan dokumen pada klasifikasi tertentu) | **Diterima** sesuai desain SKPL (pesan penolakan informatif). Dapat dimatikan bila dianggap sensitif. |
| S7 | `GET /auth/introspect?token=...` tanpa autentikasi; token di query string ikut tercatat di access log. | Kebocoran token | **Diperbaiki**: dimatikan bila `ENABLE_DEBUG_ENDPOINTS=false` (default profil prod). |
| S8 | Profil dev membuka port Postgres 5432, Ollama 11434, Keycloak 8080 ke host; koneksi DB tanpa TLS; Keycloak `sslRequired: none`. | Permukaan serangan jaringan (NFR-SEC-009, Zero Trust) | **Diperbaiki untuk produksi**: `docker-compose.prod.yml` menutup port, TLS 1.3 di proxy, Postgres SSL. Realm dev sengaja tetap `none`. |
| S9 | `POST /llm/chat` menduplikasi `/chat/sessions/{id}/query` (RBAC tetap diterapkan) tetapi tidak menyimpan riwayat. | Jalur ganda yang perlu dijaga | **Catatan**: hapus bila tidak ada klien yang memakai (`examples/`). |
| S10 | Aksi audit salah label: indeks ulang dicatat `DOC_UPLOAD`, ubah klasifikasi dicatat `ROLE_UPDATE`. | Audit menyesatkan | **Diperbaiki**: `DOC_REINDEX`, `DOC_RECLASSIFY`. |
| S11 | Deteksi prompt injection berbasis regex dapat dilewati dengan parafrase. | Prompt injection (OWASP LLM01) | **Dimitigasi berlapis**: pembatas prompt terstruktur + instruksi "data bukan instruksi" + filter RBAC sebelum retrieval sehingga LLM hanya melihat data berizin (NFR-SEC-012). Regex tetap sebagai lapisan pertama. |
| S12 | Pengguna nonaktif / sesi yang diakhiri tetap dapat memakai access token sampai kedaluwarsa. | FR-AUTH-005 | **Diperbaiki**: `sessions_revoked_at` + `is_active` diperiksa di `current_user`. |
| S13 | Indeks vektor | — | **OK**: HNSW `vector_cosine_ops` tersedia (NFR-SCL-001). |
| S14 | CORS mengizinkan origin localhost & 100.102.226.75 dengan kredensial. | Rendah | **OK** untuk dev; di profil prod frontend dan API satu origin melalui proxy. |
