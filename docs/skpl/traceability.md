# Matriks Keterlacakan Kebutuhan (DOC-09)

Kebutuhan (Lampiran A SKPL) → implementasi → pengujian. Status per 2026-11-24.
✅ terpenuhi · 🟡 sebagian / bergantung penerapan · 📄 dipenuhi melalui kebijakan/dokumentasi · ⏳ perlu verifikasi di lingkungan Docker

## Fungsional

| ID | Implementasi | Pengujian | Status |
|---|---|---|---|
| FR-AUTH-001 | Keycloak + `auth.sync_user_to_db` | `test_4a` TestAuthModule | ✅ |
| FR-AUTH-002 | `POST /auth/login` → JWT (sub, realm roles) | `test_4a` | ✅ |
| FR-AUTH-003 | `auth.decode_token`, `current_user` | `test_4a` token invalid/expired | ✅ |
| FR-AUTH-004 | `POST /auth/logout` (revoke + `LOGOUT`) | manual | ✅ |
| FR-AUTH-005 | `services/security_service.py` (`SECURITY_ALERT`), `POST /admin/users/{id}/terminate-sessions`, `auth.ensure_session_active` | `test_5` TestSecurityAlert, TestSessionRevocation | ✅ |
| FR-QUERY-001 | `ChatPage.tsx` | manual / usability | ✅ |
| FR-QUERY-002 | `ChatSession`, `ChatMessage`, `/chat/sessions*` (+ hapus & ekspor) | manual | ✅ |
| FR-QUERY-003 | `rag_service.check_prompt_injection` + pembatas prompt | `test_4b` TestPromptInjectionSecurity, `test_5` escape tags | ✅ |
| FR-QUERY-004 | `POST /chat/messages/{id}/feedback` (dengan cek kepemilikan) | `test_4a` | ✅ |
| FR-QUERY-005 | `rag_service.execute_rag_query` (pemotongan `MAX_QUERY_CHARS`), schema `max_length` | `test_5` truncation | ✅ |
| FR-RAG-001 | `ingestion_service.create_embedding(kind="query")` | `test_4a` | ✅ |
| FR-RAG-002 | SQL pgvector `<=>` | `test_4a` retrieval | ✅ |
| FR-RAG-003 | `WHERE classification = ANY(:allowed)` | `test_4b` RBAC leakage | ✅ |
| FR-RAG-004 | `LIMIT :top_k`, ambang & margin relatif | `test_4a` | ✅ |
| FR-RAG-005 | `try/except` → `_error_result` (pesan aman) | review kode | ✅ |
| FR-RAG-006 | `ingest_document`, `reindex_all_documents`, `reembed_stale_chunks` | `test_4a` ingestion | ✅ |
| FR-RESP-001 | Prompt `<konteks_dokumen>` + `<pertanyaan>` | `test_5` | ✅ |
| FR-RESP-002 | `_ollama_chat` | `test_4a` (mock) | ✅ |
| FR-RESP-003 | ChatPage | manual | ✅ |
| FR-RESP-004 | Sitasi `[n]` + kartu sumber yang dapat diklik → `/chat/documents/{id}/preview|file` | `test_4b` TestDocumentViewerRBAC | ✅ |
| FR-ADMIN-001 | `AdminRolesPage`, `/admin/roles` | manual | 🟡 lihat temuan S5 (sumber kebenaran peran pengguna) |
| FR-ADMIN-002 | `POST /admin/documents/reindex-all`, unggah | manual | ✅ |
| FR-ADMIN-003 | `AuditorLogsPage`, `/audit/logs|verify|export-csv` | `test_4b` hash chain | ✅ |
| FR-ADMIN-004 | `AdminDashboardPage`, `/admin/dashboard/health` (+ `security_alerts`) | manual | ✅ |

## Non-fungsional

| ID | Implementasi | Pengujian / bukti | Status |
|---|---|---|---|
| NFR-SEC-001 | `document_chunks.classification` difilter per kueri | `test_4b` | ✅ |
| NFR-SEC-002 | Filter metadata di SQL pgvector | `test_4b` | ✅ |
| NFR-SEC-003 | Klasifikasi disalin ke setiap chunk saat ingest; ubah klasifikasi memperbarui chunk | `test_4a` | ✅ |
| NFR-SEC-004 | Keycloak (IdP) + tabel `roles` (kebijakan akses) | `docs/skpl/rbac-matrix.md` | 🟡 desain didokumentasikan |
| NFR-SEC-005 | Matriks `roles` + konsol Admin + `ROLE_UPDATE` | `docs/skpl/rbac-matrix.md` | ✅ |
| NFR-SEC-006 | Unggah hanya oleh Admin; `validate_upload`, `sanitize_filename`, SHA-256, deteksi duplikat | `test_5` TestUploadValidation | ✅ |
| NFR-SEC-007 | Enkripsi disk/volume atau managed DB | `docs/architecture.md` | 📄 |
| NFR-SEC-008 | KMS/CMEK penyedia cloud | `docs/architecture.md` | 📄 |
| NFR-SEC-009 | Postgres SSL + `ssl=require`, port DB tertutup (profil prod) | `docker-compose.prod.yml` | ⏳ |
| NFR-SEC-010 | LLM self-hosted (tidak ada log penyedia pihak ketiga) + `redact_pii` di log aplikasi & audit | `test_5` TestPiiRedaction | ✅ |
| NFR-SEC-011 | Regex sanitasi + templat prompt bertag + escape tag | `test_4b`, `test_5` | ✅ |
| NFR-SEC-012 | Filter RBAC sebelum konteks dibangun; hasil global hanya skor | `test_4b` | ✅ |
| NFR-SEC-013 | Validasi ekstensi, ukuran, magic bytes, teks kosong → Gagal | `test_5`, `test-documents/` | ✅ |
| NFR-SEC-014 | Embedding di baris yang sama dengan klasifikasi | review | ✅ |
| NFR-SEC-015 | Audit `QUERY` berisi user, waktu, teks kueri lengkap (PII disamarkan) | `test_5` | ✅ |
| NFR-SEC-016 | Audit `QUERY` berisi `chunk_diambil` dan `dokumen_dikutip` | `test_5` | ✅ |
| NFR-SEC-017 | `ROLE_UPDATE`, `DOC_UPLOAD`, `DOC_DELETE`, `DOC_RECLASSIFY`, `DOC_REINDEX`, `LEGAL_HOLD`, `SESSION_TERMINATE` | review | ✅ |
| NFR-SEC-018 | Rantai SHA-256, trigger append-only, retensi `AUDIT_RETENTION_DAYS` + `make audit-retention` | `test_4b`, `test_5` TestAuditRetentionChain, `make test-db` | ✅ (⏳ uji DB) |
| NFR-PERF-001 | `scripts/load_test_4c.py` | `make test-perf` | ⏳ |
| NFR-PERF-002 | Multi-worker (profil prod) | `make test-perf CONCURRENCY=500` | ⏳ |
| NFR-USA-001 | UI chat sederhana | `docs/verification/usability-test.md` | ⏳ |
| NFR-USA-002 | Kartu sitasi yang dapat diklik | manual | ✅ |
| NFR-REL-001 | Healthcheck + restart policy; HA di cloud | `docs/architecture.md` | 🟡 |
| NFR-REL-002 | Layanan `backup`, `make backup`, `make restore` | uji restore manual | ⏳ |
| NFR-SCL-001 | Indeks HNSW | `docs/architecture.md` | 🟡 |
| NFR-SCL-002 | Backend stateless + kunci advisory startup | `docker compose up --scale` | 🟡 |

## Lingkup & lingkungan (SKPL §1.2, §2.3, §2.4)

| Item | Status |
|---|---|
| Kelas pengguna CEO, Legal | ✅ peran `Manajemen` (semua klasifikasi), `Legal` + legal hold, akun uji `hana` |
| Pemisahan tugas Admin | ✅ Admin hanya membaca dokumen Public |
| LlamaIndex | 📄 ADR 0001: revisi SKPL ke pipeline kustom |
| TLS 1.3 | ✅ profil prod (nginx) |
| Penyerapan dari SharePoint/Confluence | 📄 dipindah ke pengembangan lanjutan (`skpl-corrections.md` K2) |
| Filter pencarian & notifikasi (survei) | 📄 di luar lingkup rilis ini (K8); ekspor riwayat chat ✅ |
