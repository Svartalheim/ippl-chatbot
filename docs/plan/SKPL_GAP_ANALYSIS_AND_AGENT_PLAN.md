# SKPL Gap Analysis & Execution Plan for AI Agents
**Project:** ippl-chatbot (Chatbot Cerdas & Aman)
**Reference document:** *Spesifikasi Kebutuhan Perangkat Lunak (SKPL) untuk Sistem Chatbot Cerdas & Aman* (v. 16 Nov 2025, 46 pages)
**Repo state scanned:** commit `248f65e` (docs: step-by-step setup guide)
**Scan date:** 2026-11-24
**Mode:** read-only scan. No code was changed. This file is the hand-off for executing agents.

---

## Implementation status (updated 2026-11-24)

Most tasks below have been implemented in the working tree (not committed). Current status per requirement: `docs/skpl/traceability.md`.

| Task | Status | Output |
|---|---|---|
| DOC-01, 03, 04, 05, 06, 07 | Done (PlantUML source; render to PNG) | `docs/diagrams/*.puml` |
| DOC-02 | Done | `docs/skpl/usecase-scenarios.md`, `docs/skpl/skpl-corrections.md` |
| DOC-08 | Done | `docs/skpl/rbac-matrix.md` |
| DOC-09 | Done | `docs/skpl/traceability.md` |
| DOC-10 | Done (recommends amending SKPL) | `docs/adr/0001-rag-orchestration.md` |
| CODE-01 | Done | `/chat/documents/{id}/preview|file`, `services/document_access.py`, clickable citations |
| CODE-02, 04 | Done | `rag_service.py` (`_audit_query`, `_chunk_ids`), `services/pii_service.py` |
| CODE-03 | Done | `app/audit_retention.py`, retention-aware trigger, `make audit-retention` |
| CODE-05 | Done | truncation in `execute_rag_query` |
| CODE-06 | Done | `services/security_service.py`, `POST /admin/users/{id}/terminate-sessions` |
| CODE-07, 07b | Done | `validate_upload`, SHA-256 + duplicates, `Legal` role/classification, legal hold |
| CODE-08 | Done | `DELETE /chat/sessions/{id}` + UI |
| CODE-09, 11, 12 | Done, not yet run in Docker | `docker-compose.prod.yml`, `infra/nginx`, `scripts/backup*.sh`, `scripts/restore.sh` |
| CODE-10 | Documented (deployment-level) | `docs/architecture.md` |
| CODE-13 | Partial: chat export done; search filters & notifications out of scope | `ChatPage.tsx` |
| VER-01, 02 | Done | `docs/verification/test-report.md`, `security-review.md` |
| VER-03, 04 | Open: need running stack / participants | `make test-perf`, `docs/verification/usability-test.md` |
| New finding S5 | Open: team decision on role source of truth (Keycloak vs DB) | `docs/verification/security-review.md` |

---

## 0. How agents should use this file

1. Each task has an ID (`DOC-xx`, `CODE-xx`, `VER-xx`). Take **one task per agent**.
2. Each task lists **Inputs** (files to read first), **Output** (exact files to create/modify), **Acceptance criteria**, and **Depends on**.
3. Diagrams are written as **PlantUML source** (`.puml`) under `docs/diagrams/`, then rendered to `.png` (`plantuml -tpng docs/diagrams/*.puml`). Source is the deliverable; PNG is for pasting into the SKPL Word file.
4. Write documentation text in **Bahasa Indonesia** (matches the SKPL). Code comments/commit messages follow the existing repo style (Indonesian, conventional commits).
5. **Do not** change behaviour outside a task's scope. Every CODE task must keep `pytest` green and add/extend a test.
6. Requirement IDs below use the **Lampiran A (Tabel Kebutuhan Terkonsolidasi)** numbering, because it is the most complete. Section 3.1.1/3.1.2 numbering conflicts with it (see §3, issue D1).
7. Use the PDF section numbers when referencing the SKPL (e.g. "§3.2.2").

---

## 1. Verdict (short)

| Area | Status |
|---|---|
| Core functional scope (login/logout, RAG chat, citations, feedback, history, admin docs/roles/dashboard, auditor logs) | **Largely met** |
| RBAC + metadata filtering in pgvector, prompt-injection guard, append-only hash-chained audit log | **Met** (strongest part of the project) |
| Security/infra NFRs (TLS, encryption at rest, CMEK, DB auth+TLS, PII, backup, retention, 99.9% uptime, horizontal scaling) | **Mostly not met / not evidenced** |
| User classes from §2.3 (CEO, Penasihat Hukum/Legal) | **Partially met** – no Legal role/classification, CEO ≈ "Manajemen" |
| Tech stack from §2.4 (LlamaIndex orchestration) | **Not met** – RAG is hand-written (SQL + httpx), LlamaIndex is not a dependency |
| SKPL analysis models (§3.2: use case, scenarios, class, activity) | **Exist but incomplete and out of sync with the code** |
| Diagrams inside the repo | **None** – no `docs/`, no `.puml`/`.mmd` files |

---

## 2. Requirement traceability matrix (as-built)

Legend: ✅ met · 🟡 partial · ❌ missing · ❓ needs verification

### 2.1 Functional (Lampiran A)

| ID | Requirement (short) | Status | Evidence in repo | Gap → Task |
|---|---|---|---|---|
| FR-AUTH-001 | Integrate with user database | ✅ | Keycloak realm `infra/keycloak/dev-realm.json`; users synced to `users` table (`models.User.keycloak_sub`) | SKPL text says passwords are hashed in local DB (§3.2.1.3) – code delegates to Keycloak → **DOC-02** |
| FR-AUTH-002 | Receive JWT with user ID + roles after login | ✅ | `routers/auth.py POST /auth/login`, `auth.py` | – |
| FR-AUTH-003 | Validate JWT signature + expiry per request | ✅ | `auth.py current_user`, `require_roles` | – |
| FR-AUTH-004 | Secure logout invalidating session | ✅ | `POST /auth/logout` revokes refresh token, logs `LOGOUT` | – |
| FR-AUTH-005 | Log security alerts & optionally terminate active session | 🟡 | `LOGIN_FAILED`, `PROMPT_INJECTION`, `QUERY_DENIED` logged | No session termination (admin force-logout / auto-revoke after N injections) → **CODE-06** |
| FR-QUERY-001 | Text chat UI for natural-language queries | ✅ | `frontend/src/pages/ChatPage.tsx` | – |
| FR-QUERY-002 | Store conversation history in a user session | ✅ | `ChatSession`, `ChatMessage`; `GET /chat/sessions`, `/messages` | No delete-history (`hapusRiwayat()` in class diagram) → **CODE-08** |
| FR-QUERY-003 | Sanitize input against prompt injection | ✅ | `rag_service.check_prompt_injection` (regex) | Regex-only; document limits in SKPL → **DOC-02** |
| FR-QUERY-004 | Feedback on answer quality | ✅ | `POST /chat/messages/{id}/feedback`, thumbs up/down in ChatPage | – |
| FR-QUERY-005 | Truncate/segment input over a limit | ❓ | No `max_length` found on query schema | → **CODE-05** |
| FR-RAG-001 | Embed sanitized query | ✅ | `ingestion_service.create_embedding` (Ollama `nomic-embed-text`, 768-d) | – |
| FR-RAG-002 | Similarity search in vector DB | ✅ | `rag_service` SQL on `document_chunks.embedding` | – |
| FR-RAG-003 | Metadata filter by user role/permissions | ✅ | `WHERE dc.classification = ANY(:allowed_classifications)` | – |
| FR-RAG-004 | Retrieve top-K chunks | ✅ | `rag_service` | – |
| FR-RAG-005 | Fallback + safe error message if vector DB fails | 🟡 | `try/except` + "fallback" warnings in `rag_service` | Verify user-facing message hides technical detail → **VER-02** |
| FR-RAG-006 | Incremental embedding updates | ✅ | `ingest_document`, `reembed_stale_chunks`, `reindex_all_documents` | – |
| FR-RESP-001 | Build prompt with query + chunks | ✅ | `rag_service` | Confirm structured delimiters (NFR-SEC-011) → **VER-02** |
| FR-RESP-002 | Send prompt to configured LLM | ✅ | Ollama `llama3.2:3b` | – |
| FR-RESP-003 | Show answer in chat UI | ✅ | ChatPage | – |
| FR-RESP-004 | Verifiable, **clickable** citations | 🟡 | Inline `[1]`, `[2]` + citation list | Document viewer calls `/admin/documents/{id}/preview|file` (Admin-only router) → non-admin users probably can't open the cited source → **CODE-01** |
| FR-ADMIN-001 | Admin UI: role/group ↔ document permission mapping | ✅ | `AdminRolesPage.tsx`, `GET/POST/PUT /admin/roles`, `PUT /admin/users/{id}/role` | – |
| FR-ADMIN-002 | Admin trigger manual ingest / reindex | ✅ | `POST /admin/documents/reindex-all`, upload | – |
| FR-ADMIN-003 | Auditor read-only search/view of all logs | ✅ | `GET /audit/logs` (filters), `/audit/verify`, `/audit/export-csv`, `AuditorLogsPage.tsx` | – |
| FR-ADMIN-004 | Admin system-health dashboard | ✅ | `GET /admin/dashboard/health`, `AdminDashboardPage.tsx` | – |

### 2.2 Non-functional (Lampiran A)

| ID | Requirement (short) | Status | Evidence | Gap → Task |
|---|---|---|---|---|
| NFR-SEC-001 | RBAC at chunk level | ✅ | `document_chunks.classification` filtered per query | – |
| NFR-SEC-002 | Access control via metadata filtering in vector DB | ✅ | same | – |
| NFR-SEC-003 | Auto-tag chunks with classification at ingest | ✅ | `ingestion_service` copies `Document.classification` to chunks | – |
| NFR-SEC-004 | Central authorization service | 🟡 | Keycloak for authN; permissions live in app `roles` table | Document the design decision (Keycloak = IdP, app DB = policy store) → **DOC-09** |
| NFR-SEC-005 | Explicit auditable role/permission matrix | 🟡 | `roles.allowed_classifications`, `can_*` flags; admin UI | Matrix not in SKPL; `ROLE_UPDATE` audited ✅ → **DOC-08** |
| NFR-SEC-006 | Ingest only from trusted, validated sources | 🟡 | Admin-only upload | No source allow-list / file signature / checksum → **CODE-07** |
| NFR-SEC-007 | Vector DB encrypted at rest (AES-256) | ❌ | Only `pgcrypto` extension enabled, unused | → **CODE-10** |
| NFR-SEC-008 | CMEK support | ❌ | – | Document as deployment-level (cloud KMS) → **CODE-10 / DOC-09** |
| NFR-SEC-009 | Orchestrator ↔ vector DB authenticated & encrypted | 🟡 | Password auth via `DATABASE_URL` | No `sslmode=require` → **CODE-09** |
| NFR-SEC-010 | No PII in LLM provider logs | 🟡 | LLM is self-hosted (Ollama), so no third-party logs | No PII redaction in prompt or in app logs (`logger` prints `query[:80]`, `answer_text[:200]`) → **CODE-04** |
| NFR-SEC-011 | Input sanitization + structured prompt template with delimiters | ❓ | Injection regex exists | Verify delimiters in prompt → **VER-02** |
| NFR-SEC-012 | LLM only sees authorized data | ✅ | Filter applied before prompt build | Also check `routers/llm.py POST /llm/chat` doesn't bypass it → **VER-02** |
| NFR-SEC-013 | Ingestion pipeline validation checks | 🟡 | Corrupt/scanned-PDF handling (`test-documents/Dokumen Rusak.pdf`, `Hasil Scan Tanpa Teks.pdf`) | No size/MIME/magic-byte checks found → **CODE-07** |
| NFR-SEC-014 | Embeddings classified/protected like source text | ✅ | Classification on every chunk row | – |
| NFR-SEC-015 | Log every query: user ID, timestamp, query text | 🟡 | `QUERY` audit entries | `detail` stores only `query[:40]…` → full text not logged → **CODE-02** |
| NFR-SEC-016 | Log which chunks were retrieved per query | 🟡 | `detail` has "N sumber" count | Chunk/document IDs not recorded → **CODE-02** |
| NFR-SEC-017 | Log all admin actions incl. role changes | ✅ | `ROLE_UPDATE`, `DOC_UPLOAD`, `DOC_DELETE`, `DOC_VIEW` | Check reindex + classification change are logged → **VER-02** |
| NFR-SEC-018 | Audit log tamper-proof + **configurable retention** | 🟡 | SHA-256 hash chain, DB trigger blocks UPDATE/DELETE/TRUNCATE, `/audit/verify` | No retention setting → **CODE-03** |
| NFR-PERF-001 | p95 < 5 s | ❓ | `scripts/load_test_4c.py` exists | No recorded result in repo → **VER-03** |
| NFR-PERF-002 | 500 concurrent users | ❓ | load test supports `--concurrency 500` | Backend runs `uvicorn --reload` single process → **CODE-12**, **VER-03** |
| NFR-USA-001 | Learnable in ≤ 10 min | ❓ | – | Usability test script → **VER-04** |
| NFR-USA-002 | Clear citations navigable to source | 🟡 | see FR-RESP-004 | → **CODE-01** |
| NFR-REL-001 | 99.9 % uptime | ❌ | Docker Compose, single instances, no healthcheck/restart policy evidence | Document as deployment target + add restart policies → **CODE-12**, **DOC-07** |
| NFR-REL-002 | Automatic backup & restore | ❌ | No `pg_dump`/backup script | → **CODE-11** |
| NFR-SCL-001 | Horizontal scaling for 10× docs | ❌ | – | Architecture doc + HNSW/IVFFlat index check → **DOC-07**, **VER-02** |
| NFR-SCL-002 | 5× users w/o redesign | ❌ | – | Stateless backend + workers → **CODE-12** |

### 2.3 Scope / environment items from §1.2, §2.3, §2.4

| Item | Status | Note → Task |
|---|---|---|
| User classes: CEO, Karyawan, HR, Finance, **Penasihat Hukum (Legal)**, Admin, Auditor | 🟡 | Code roles: Karyawan, HR, Finance, Manajemen, Admin, Auditor. No Legal role, no `Legal` classification, no "legal hold". CEO ↔ Manajemen mapping undocumented → **CODE-07b**, **DOC-02** |
| Admin has **no default access to sensitive content** (separation of duties) | ❓ | Admin can open any document via `/admin/documents/{id}/file` → contradicts §2.3 → **VER-02**, maybe **CODE-01** |
| Auditor cannot change config or read document content | ✅/❓ | Audit router allows `Auditor, Admin`; verify Auditor has no route to document content → **VER-02** |
| Ingestion from SharePoint/Confluence | ❌ | Manual upload only. Either implement or move to out-of-scope in SKPL → **DOC-02** |
| Orchestration with **LlamaIndex** | ❌ | Not used. Decide: adopt or amend SKPL (ADR) → **DOC-10** |
| Ollama + Llama 3 | ✅ | `llama3.2:3b` |
| PostgreSQL + pgvector | ✅ | – |
| React + TypeScript SPA | ✅ | Vite + Tailwind |
| HTTPS / TLS 1.3 | ❌ | Keycloak `sslRequired: none`; no reverse proxy with TLS → **CODE-09** |
| Survey extras: keyword search, filters (date/category/type/author), export chat, notifications | ❌ | Not in FR tables either → **DOC-02** (decide in/out of scope), optional **CODE-13** |

---

## 3. Problems inside the SKPL document itself

These must be fixed regardless of code (the document is the formal deliverable).

| # | Issue | Where |
|---|---|---|
| D1 | **Two conflicting requirement lists.** §3.1.1/3.1.2 and Lampiran A use the same IDs for different requirements (e.g. FR-AUTH-002 = "username+password" vs "receive JWT"; FR-QUERY-003 = feedback vs sanitization; FR-ADMIN-003 = admin add/delete docs vs auditor logs; NFR-SEC-001..009 vs 001..018). | §3.1, Lampiran A |
| D2 | **Scope contradiction:** §1.2 says the system is read-only and document management is out of scope, but FR-ADMIN-003 (§3.1.1) and use case "Kelola Dokumen" let admins upload/delete documents. | §1.2 vs §3.1.1, §3.2.1.8 |
| D3 | User classes in §2.3 (CEO, HR, Finance, Legal) don't appear in the use case diagram (only "Pengguna"). | §2.3 vs §3.2.1 |
| D4 | All 10 use case scenarios have **empty "Skenario Eksepsional"** sections; several main flows stop mid-way (Login has no redirect/failure step, Logout has no step after "receive request", Verifikasi Autentikasi has broken numbering "4.", "5."). | §3.2.1.1–10 |
| D5 | Verifikasi Autentikasi describes hashing passwords in the local DB; the system uses Keycloak (§2.6). | §3.2.1.3 |
| D6 | Use case diagram relations: "History Pertanyaan" drawn as `<<extend>>` of "Mengajukan Pertanyaan" (it's an independent user goal); no `<<include>>` for JWT validation / RBAC filtering; implemented use cases missing (see DOC-01). | §3.2.1 |
| D7 | Class diagram is out of sync with the implementation (see DOC-04 table). | §3.2.2 |
| D8 | Only 3 activity diagrams; no sequence diagram, ERD, deployment/architecture diagram, though §2.4 describes a multi-component architecture. | §3.2.3 |
| D9 | "HTTPS 1.3" should be "TLS 1.3"; "artificial intellegent" typo. | §2.4.1, §2.2 |
| D10 | Survey findings (filters, export, notifications) are not traced into any FR, nor explicitly excluded. | Hasil Survey vs §3.1 |
| D11 | ISO 29148 checklist claims all requirements are Unambiguous/Singular/Verifiable, but several aren't (e.g. NFR-USA-001 has no measurement method; NFR-SEC-008 CMEK has no acceptance test). | Lampiran A |

---

## 4. Work packages

### WP-DOC — Analysis models & SKPL corrections (can start immediately, all parallel except where noted)

---

#### DOC-01 — Use case diagram (as-built + SKPL-aligned)
- **Inputs:** this file §2–3; SKPL §2.3, §3.2.1; `backend/app/routers/*.py`; `frontend/src/App.tsx` (routes); `backend/app/seed.py` (roles).
- **Output:** `docs/diagrams/usecase.puml` → `usecase.png`.
- **Content requirements:**
  - System boundary "Sistem Chatbot Cerdas & Aman".
  - Actors: `Pengguna` (abstract) with generalizations `Karyawan`, `Spesialis SDM (HR)`, `Analis Keuangan`, `Manajemen/CEO`, `Penasihat Hukum` (mark Legal as *planned* if CODE-07b not done); `Administrator Sistem`; `Auditor Kepatuhan`; secondary actors on the right: `Keycloak (IdP)`, `Ollama LLM`.
  - Use cases (keep SKPL names, add missing ones that the code implements):
    Login Aplikasi, Logout, Verifikasi Autentikasi (`<<include>>` from Login, linked to Keycloak), Mengajukan Pertanyaan (`<<include>>` Validasi Token JWT, `<<include>>` Filter Akses RBAC, `<<include>>` Catat Log Audit), Lihat Sitasi & Dokumen Sumber (`<<extend>>` Mengajukan Pertanyaan), Beri Feedback Jawaban (`<<extend>>`), Kelola Sesi Percakapan / History Pertanyaan (independent), Kelola Peran & Izin (incl. Ubah Peran Pengguna), Kelola Dokumen (Unggah, Hapus, Ubah Klasifikasi, Indeks Ulang as `<<extend>>` or sub-use-cases), Lihat Dasbor Kesehatan Sistem, Tinjau Log Audit (`<<extend>>` Verifikasi Rantai Hash, `<<extend>>` Ekspor CSV).
  - Do **not** connect Admin to document-content use cases if §2.3 separation of duties is kept.
- **Acceptance:** every use case maps to ≥1 endpoint or UI page (add a comment block in the `.puml` listing the mapping); renders without errors.

#### DOC-02 — Rewrite use case scenarios + fix requirement text
- **Depends on:** DOC-01 (use case list).
- **Inputs:** SKPL §3.2.1.1–10, §1.2, §2.3, §3.1, Lampiran A; routers; ChatPage/LoginPage/Admin*/Auditor* pages.
- **Output:** `docs/skpl/usecase-scenarios.md` (one table per use case, same columns as SKPL: Nama, Deskripsi, Aktor, Pre/Post-Kondisi, Skenario Utama [Aktor|Sistem], Skenario Eksepsional) and `docs/skpl/skpl-corrections.md` (list of edits to paste into the Word file).
- **Content requirements:**
  - Complete main flows to the post-condition (e.g. Login: redirect per role → `/chat`, `/admin`, `/auditor`).
  - Write ≥2 alternative flows per use case from real code behaviour: wrong credentials (`LOGIN_FAILED`), expired JWT → refresh, `PROMPT_INJECTION` blocked, `QUERY_DENIED` (answer only in unauthorized docs), no relevant document found, Ollama timeout / vector DB down, upload of corrupt / scanned PDF, unsupported file type, hash-chain verification failure, empty filter result.
  - Fix D1 (single unified ID list = Lampiran A; renumber §3.1.1/3.1.2 to match), D2 (move "Kelola Dokumen" into scope, keep "editing source repositories" out of scope), D5 (authentication via Keycloak), D9, D10 (state which survey features are in/out of scope), D11.
- **Acceptance:** no empty "Skenario Eksepsional"; every alternative flow cites the audit action or HTTP status the code produces.

#### DOC-03 — Activity diagrams (update 3 + add 3)
- **Inputs:** SKPL §3.2.3; `rag_service.py`, `ingestion_service.py`, `audit_service.py`, `routers/auth.py`.
- **Output:** `docs/diagrams/activity-*.puml` (swimlanes: Pengguna/Admin/Auditor | Frontend | Backend FastAPI | Keycloak | PostgreSQL+pgvector | Ollama):
  1. `activity-query.puml` – Mengajukan Pertanyaan. Must include small-talk shortcut, injection check, RBAC filter, `QUERY_DENIED` branch (global search finds unauthorized match), not-found branch, LLM failure branch, audit write.
  2. `activity-kelola-dokumen.puml` – upload → extract (PDF/DOCX) → chunk (500/100) → embed → store → status `Memproses/Aktif/Gagal`; delete; reindex.
  3. `activity-audit.puml` – Auditor filter, view, verify chain, export CSV.
  4. **new** `activity-login-logout.puml` – Keycloak token flow, refresh, logout revoke.
  5. **new** `activity-kelola-peran.puml` – edit role permissions / user role, `ROLE_UPDATE` logged.
  6. **new** `activity-feedback.puml` (small).
- **Acceptance:** each decision node matches a real `if` branch in code (reference function names in notes).

#### DOC-04 — Class diagram (analysis + implementation)
- **Inputs:** SKPL §3.2.2; `backend/app/models.py`, `schemas.py`, `services/*.py`, `routers/*.py`.
- **Output:**
  - `docs/diagrams/class-domain.puml` – corrected analysis-level diagram (replaces SKPL §3.2.2).
  - `docs/diagrams/class-implementation.puml` – service/router layer (FastAPI routers, `RagService` functions, `IngestionService`, `AuditService`, `AuthDependency`) with dependencies.
- **Known mismatches to resolve (SKPL → code):**

  | SKPL class | Code | Fix in diagram |
  |---|---|---|
  | `User` + subclasses `admin`, `karyawan`, `auditor` (inheritance) | single `User` with FK to `Role` | Model as `User` —* `Role`; show role capabilities as `Role` attributes (`allowed_classifications`, `can_manage_docs`, `can_manage_rbac`, `can_view_audit`). Optionally keep actor subclasses only in the use case diagram. |
  | `User.password`, `userID: int`, `departemen` | no password (Keycloak), `id: UUID`, `keycloak_sub`, `full_name`, `email`, `is_active`, `last_login_at`; no department | Use real fields; drop password; note departemen not implemented (or add via CODE) |
  | `peran` (peranID, namaPeran, izinAkses) | `Role` | rename/align |
  | `dokumen` (…, klasifikasiData enum {Public, HR, Finance, Confidential}, lokasiPenyimpanan) | `Document` (filename, file_type, file_size_bytes, classification, status, error_message, chunk_count, uploaded_by) | align; add `Legal` if CODE-07b |
  | — | `DocumentChunk` (content, page_number, section_title, classification, embedding Vector(768), metadata_json) | **add** (core of RAG/RBAC) |
  | `chat pertanyaan` (pertanyaanTeks + jawabanTeks in one row) | `ChatMessage` (one row per sender, status, citations_json, latency_ms, blocked_classification) | align |
  | `history` | `ChatSession` (title, user_id, timestamps) | rename to ChatSession / Riwayat |
  | `feedback` (nilai enum) | `Feedback` (is_positive bool, comment) | align |
  | `log` | `AuditLog` (actor_name, actor_role, ip_address, action, detail, status, prev_hash, curr_hash) | align, show hash-chain |
  | `dashboard_kesehatan` (persisted class) | computed by `GET /admin/dashboard/health` → `DashboardHealthResponse` | show as non-persistent DTO / `<<boundary>>` |
- **Relationships & notation (explicit):**
  - `User` "0..*" — "1" `Peran` (association; no inheritance between User and role classes).
  - `Dokumen` "1" ◆— "0..*" `DocumentChunk` (composition: chunks are deleted with the document, `ON DELETE CASCADE`).
  - `ChatSession` "1" ◆— "0..*" `ChatMessage` (composition, `ON DELETE CASCADE`).
  - `User` "1" — "0..*" `ChatSession`; `User` "0..1" — "0..*" `Dokumen` (uploader, `ON DELETE SET NULL`).
  - `ChatMessage` "1" — "0..1" `Feedback`; `User` "0..1" — "0..*" `Feedback`.
  - `User` "0..1" — "0..*" `AuditLog` (actor, `ON DELETE SET NULL`); show the self-reference `prevHash → currHash` as a note.
  - `DasborKesehatan` as `<<boundary>>` / DTO with a dependency (dashed arrow) on `ChatMessage` and `AuditLog`, not a persisted class.
- **Methods (analysis level):** put each method on the class that owns the data, not on role subclasses. Minimum set:
  - `User`: `login()`, `logout()`
  - `Peran`: `tambahPeran()`, `ubahIzin()`
  - `Dokumen`: `unggah()`, `hapus()`, `ubahKlasifikasi()`, `indeksUlang()`
  - `DocumentChunk`: `buatEmbedding()`
  - `ChatSession`: `buatSesi()`, `ambilRiwayat()`
  - `ChatMessage`: `ajukanPertanyaan()`, `simpanJawaban()`
  - `Feedback`: `simpanFeedback()`
  - `AuditLog`: `catatLog()`, `filterLog()`, `verifikasiRantai()`, `eksporCSV()`
  - `DasborKesehatan`: `ambilMetrik()`
- **Enums:** `Klasifikasi {Public, HR, Finance, Confidential}` (+`Legal` only if CODE-07b is done), `StatusDokumen {Memproses, Aktif, Gagal}`, `Pengirim {user, assistant}`.
- **Acceptance:** every attribute in `class-domain.puml` exists in `models.py` (or is explicitly marked *planned*); multiplicities match FKs.

#### DOC-05 — Sequence diagrams (new)
- **Output:** `docs/diagrams/seq-login.puml`, `seq-query-rag.puml`, `seq-upload-document.puml`, `seq-audit-verify.puml`.
- **Acceptance:** participants and calls match function names in `auth.py`, `rag_service.py`, `ingestion_service.py`, `audit_service.py`.

#### DOC-06 — ERD (new)
- **Inputs:** `infra/postgres/init.sql`, `models.py`.
- **Output:** `docs/diagrams/erd.puml` (PK/FK, types, `ON DELETE` rules, pgvector column, audit trigger noted).

#### DOC-07 — Architecture & deployment diagram (new)
- **Inputs:** `docker-compose.yml`, `Makefile`, `README-dev-environment.md`, SKPL §2.4.
- **Output:** `docs/diagrams/deployment.puml` (current Docker Compose) + `docs/architecture.md` section "Target produksi" describing how NFR-REL-001, NFR-SCL-001/002, NFR-SEC-007/008/009 are met (reverse proxy TLS 1.3, N backend replicas, managed Postgres with encryption at rest + KMS/CMEK, backups).
- **Depends on:** nothing; update after CODE-09/11/12.

#### DOC-08 — RBAC matrix (NFR-SEC-005)
- **Inputs:** `seed.py`, `models.Role`, `auth.require_roles` usages.
- **Output:** `docs/skpl/rbac-matrix.md`: rows = roles, columns = classifications (Public/HR/Finance/Confidential/[Legal]) + capabilities (manage docs, manage RBAC, view audit, open source document) + API route groups. Mark the §2.3 conflicts (Admin content access).

#### DOC-09 — Traceability appendix
- **Depends on:** all CODE/VER tasks finished (or run once now and again at the end).
- **Output:** `docs/skpl/traceability.md` – the §2 tables of this file, updated with final status and file/test references (requirement → code → test).

#### DOC-10 — ADR: LlamaIndex
- **Output:** `docs/adr/0001-rag-orchestration.md` (use the `engineering:architecture` format). Options: (a) amend SKPL §2.4.2.2 to "custom RAG pipeline with SQL + httpx" with justification (control over RBAC filter SQL, fewer deps); (b) migrate to LlamaIndex `PGVectorStore` with metadata filters. Recommend one; if (a), add the text change to `skpl-corrections.md`.

---

### WP-CODE — Implementation gaps (each needs a test; ordered by priority)

| ID | Priority | Task | Files likely touched | Acceptance |
|---|---|---|---|---|
| **CODE-01** | Must | Non-admin citation viewer: add `GET /chat/documents/{id}/preview` (and optional `/file`) authorized by the caller's `allowed_classifications`, log `DOC_VIEW`; point `DocumentViewerModal` to it from ChatPage. Decide/implement whether Admin keeps content access (§2.3 separation of duties). | `routers/chat.py` (or new `routers/documents.py`), `components/DocumentViewerModal.tsx`, `ChatPage.tsx` | Karyawan can open a Public citation, gets 403 on HR doc; test in `test_4b_security.py` |
| **CODE-02** | Must | Audit `QUERY` entries store full query text (after PII redaction) and the list of retrieved `chunk_id`/`document_id` (NFR-SEC-015/016). Consider a structured JSON `detail`. Keep hash chain valid. | `services/rag_service.py`, `services/audit_service.py` | New test asserts chunk IDs present; `/audit/verify` still OK |
| **CODE-03** | Must | Configurable audit retention (`AUDIT_RETENTION_DAYS` in `config.py`/.env); archival job that exports + seals old rows without breaking chain (e.g. checkpoint row with last hash) — trigger must still block ad-hoc delete. | `config.py`, `audit_service.py`, `init.sql`, Makefile target | Test: retention setting read; verify passes after archival |
| **CODE-04** | Must | PII redaction utility (email, phone, NIK 16-digit, account numbers) applied to: app logger output, audit `detail`, and optionally prompt context logging. | new `services/pii.py`, `rag_service.py` | Unit tests for each pattern |
| **CODE-05** | Should | Query length limit (FR-QUERY-005): `max_length` on request schema + server-side truncation/segmentation with user notice. | `schemas.py`, `rag_service.py`, ChatPage char counter | Test: 10k-char query handled without 500 |
| **CODE-06** | Should | FR-AUTH-005: security alert record (e.g. `SECURITY_ALERT` after N `PROMPT_INJECTION`/`LOGIN_FAILED` within window) + admin "terminate session" (Keycloak admin API logout user). Show alerts on dashboard. | `auth.py`, `routers/admin.py`, `AdminDashboardPage.tsx` | Test for alert threshold |
| **CODE-07** | Must | Ingestion validation (NFR-SEC-006/013): allowed extensions + magic-byte check, max size, SHA-256 checksum stored on `Document`, duplicate detection, reject empty-text docs with clear status. | `ingestion_service.py`, `routers/admin.py`, `models.Document` | Tests with `test-documents/*` |
| **CODE-07b** | Should | Add `Legal` classification + `Penasihat Hukum` role (seed + Keycloak realm); document CEO = `Manajemen` with all classifications. Optional `legal_hold` flag on `Document` blocking delete. | `seed.py`, `dev-realm.json`, `models.py`, Admin pages | RBAC test for Legal |
| **CODE-08** | Could | Delete own chat session (`DELETE /chat/sessions/{id}`) + UI button (class diagram `hapusRiwayat()`). | `routers/chat.py`, ChatPage | Test: owner can delete, other user 404 |
| **CODE-09** | Must | Transport security: Nginx/Caddy reverse proxy with TLS 1.3 (self-signed for dev), Keycloak `sslRequired: external`, Postgres `ssl=on` + `sslmode=require` in `DATABASE_URL`. | `docker-compose.yml`, `infra/`, `.env.example` | `curl -v` shows TLSv1.3; README updated |
| **CODE-10** | Should | Encryption at rest: document volume/disk encryption + managed-DB KMS (CMEK) for prod; optionally pgcrypto for `document_chunks.content`. Must not break vector search (embeddings stay plaintext; justify). | docs + maybe `models.py` | Written justification in `docs/architecture.md` |
| **CODE-11** | Must | Backup/restore: `scripts/backup.sh` (`pg_dump` + `data/documents` tarball, timestamped, rotation), `scripts/restore.sh`, compose `backup` service with cron; restore drill documented. | `scripts/`, `docker-compose.yml`, Makefile | Restore into empty DB + `/audit/verify` OK |
| **CODE-12** | Should | Production profile: backend Dockerfile without `--reload`, `--workers` / gunicorn, `restart: unless-stopped`, healthchecks for all services, stateless backend (no local-file dependency → shared volume/object storage). | `backend/Dockerfile`, `docker-compose.yml` (+ `docker-compose.prod.yml`) | `docker compose up --scale backend=3` works behind proxy |
| **CODE-13** | Could | Survey extras (only if DOC-02 puts them in scope): document filter (classification/type/date) in chat, export chat session to PDF/MD. | ChatPage, `rag_service` | – |

---

### WP-VER — Verification (evidence for the SKPL)

| ID | Task | Output |
|---|---|---|
| **VER-01** | Run `make test` / `pytest`; record counts (currently 24 unit + 10 security + 4 DB integration test functions). Fix nothing outside scope; report failures. | `docs/verification/test-report.md` |
| **VER-02** | Security review checklist (read code, run requests): `/llm/chat` RBAC bypass?; prompt template delimiters; fallback error messages leak nothing; Admin/Auditor content access vs §2.3; reindex & classification change audited; pgvector index type (HNSW/IVFFlat) present; CORS list. Use the `engineering:code-review` skill. | `docs/verification/security-review.md` with findings → new CODE tasks if needed |
| **VER-03** | Run `scripts/load_test_4c.py` at 50 and 500 concurrency; record p95 vs 5 s target and hardware used. | `docs/verification/load-test.md` |
| **VER-04** | Usability test script for NFR-USA-001 (task list, timer, 3–5 testers, SUS questionnaire). | `docs/verification/usability-test.md` |

---

## 5. Execution order

```
Phase 1 (parallel, docs only, no code risk):
  DOC-01 ─┐
  DOC-03   │
  DOC-04   ├─► DOC-02 (needs DOC-01 list)
  DOC-05   │
  DOC-06   │
  DOC-08   │
  DOC-10  ─┘
  VER-01, VER-02  (read-only; VER-02 may add CODE tasks)

Phase 2 (code, Must first):
  CODE-01, CODE-02+CODE-04 (same agent; both touch rag_service/audit), CODE-07, CODE-09, CODE-11
  then CODE-03, CODE-05, CODE-06, CODE-07b, CODE-12
  then CODE-08, CODE-10, CODE-13

Phase 3:
  VER-03, VER-04
  DOC-07 (final), DOC-09 (final traceability), re-render all diagrams,
  re-run DOC-01/04 diffs if Phase 2 changed models or endpoints.
```

Conflict hotspots (don't run concurrently): `rag_service.py` (CODE-02, 04, 05), `models.py` (CODE-07, 07b, 03), `docker-compose.yml` (CODE-09, 11, 12), `ChatPage.tsx` (CODE-01, 05, 08, 13).

---

## 6. Prompt template for executing agents

```
You are working in the ippl-chatbot repo (FastAPI + PostgreSQL/pgvector + Ollama + Keycloak + React/TS).
Read docs/plan/SKPL_GAP_ANALYSIS_AND_AGENT_PLAN.md, sections 0, 2, 3 and task <TASK-ID>.
Do ONLY <TASK-ID>. Read the listed Inputs first.
Produce exactly the listed Output files. Documentation in Bahasa Indonesia.
For diagrams: PlantUML source in docs/diagrams/, render PNG, verify it renders.
For code: add/extend tests under backend/tests/, run pytest, keep audit hash chain verifiable.
Finish by updating the task's Status row in docs/skpl/traceability.md (create it if missing) with file + test references.
Do not commit unless asked; summarise changes and any new gaps found.
```
