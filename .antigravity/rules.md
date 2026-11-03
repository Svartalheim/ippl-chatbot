# Aturan Arsitektur & Pedoman Pengembangan Sistem Chatbot Cerdas & Aman (IPPL)

File ini menetapkan aturan arsitektur, standar keamanan, matriks RBAC, dan konvensi implementasi yang **wajib dipatuhi di seluruh tahapan pengembangan** pada repositori ini.

---

## 1. Stack Utama & Konfigurasi Arsitektur

### 1.1 Backend
- **Runtime & Framework**: Python 3.11+, FastAPI.
- **ORM & Database Driver**: SQLAlchemy 2.0 Async dengan `asyncpg`. Selalu gunakan `AsyncSession` dari `backend/app/db.py` (dependency `get_session`).
- **Vector & Dokumen**: `pgvector`, `pypdf`, `python-docx`, `python-multipart`.
- **HTTP & Komunikasi**: `httpx` (async) untuk komunikasi dengan Keycloak dan Ollama.

### 1.2 Database
- **DBMS**: PostgreSQL 16 dengan ekstensi `vector` aktif (`image: pgvector/pgvector:pg16`).
- **Ekstensi Wajib**:
  - `CREATE EXTENSION IF NOT EXISTS vector;`
  - `CREATE EXTENSION IF NOT EXISTS pgcrypto;` (jika dibutuhkan untuk UUID/kriptografi SQL).
- **Indeks Vektor**: Gunakan indeks HNSW pada kolom `embedding` (`USING hnsw (embedding vector_cosine_ops)`).

### 1.3 Autentikasi & Otorisasi (Keycloak 26.0)
- **Modul Auth**: `backend/app/auth.py` menggunakan `jwt.PyJWKClient` untuk validasi signature token JWT dari Keycloak.
- **Dependency Utama**: `current_user` mengembalikan objek `UserInfo`.
- **Endpoint Invarian (DILARANG MERUSAK)**:
  - `POST /auth/login`
  - `POST /auth/refresh`
  - `POST /auth/logout`
  - `GET /auth/userinfo`
  - `GET /me`
  - `GET /health`
  Seluruh endpoint di atas harus tetap berfungsi normal dan kompatibel dengan implementasi yang sudah ada.

### 1.4 LLM & Embedding (Ollama)
- **Ollama Host**: Menggunakan `settings.ollama_url` (default `http://ollama:11434` di container, atau sesuai konfigurasi `.env`).
- **Model Chat / LLM**: `settings.ollama_model` (default `llama3.2:3b` atau `llama3`).
- **Model Embedding**: `settings.ollama_embed_model` (default `nomic-embed-text`, dimensi vektor: **768**).
- Mode testing/mock embedding deterministik (`ALLOW_MOCK_EMBEDDING=true`) hanya diizinkan saat testing/seeding awal jika Ollama belum siap.

### 1.5 Frontend
- **Lokasi**: Seluruh kode antarmuka berada di dalam direktori `frontend/`.
- **Teknologi**: React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons (`lucide-react`).
- **Integrasi**: Single Page Application (SPA) yang terintegrasi penuh dengan API FastAPI dan Keycloak Token Flow.

---

## 2. Klasifikasi Dokumen & Matriks RBAC (Role-Based Access Control)

### 2.1 Tingkat Klasifikasi Dokumen (4 Tingkat)
Setiap dokumen dan chunk teks memiliki label klasifikasi:
1. `Public`
2. `HR`
3. `Finance`
4. `Confidential`

### 2.2 Matriks Akses Peran Pengguna (6 Peran)

| Peran Pengguna | Dokumen yang Boleh Diakses | Hak Akses Tambahan | Catatan |
| :--- | :--- | :--- | :--- |
| **`Karyawan`** | `['Public']` | Standar Chat | Peran default untuk seluruh karyawan biasa. |
| **`HR`** | `['Public', 'HR']` | Standar Chat | Akses ke dokumen internal divisi HR. |
| **`Finance`** | `['Public', 'Finance']` | Standar Chat | Akses ke dokumen internal divisi Finance. |
| **`Manajemen`** | `['Public', 'HR', 'Finance', 'Confidential']` | Standar Chat | Akses ke seluruh klasifikasi dokumen perusahaan. |
| **`Admin`** | `['Public']` | `can_manage_docs = true`<br>`can_manage_rbac = true` | Pengelolaan dokumen (upload/reindex/delete) dan pengaturan peran & izin. |
| **`Auditor`** | `[]` (Tidak ada akses dokumen chat) | `can_view_audit = true` (Read-only) | Tinjau log audit, verifikasi integritas rantai hash, dan ekspor log CSV. |

### 2.3 Aturan Eksekusi Query RAG & Deteksi Lintas-Klasifikasi
1. **Filter RBAC Similarity Search**:
   - Query pencarian chunk ke `document_chunks` wajib difilter menggunakan:
     `WHERE classification = ANY(:allowed_classifications)`
2. **Deteksi Penolakan Lintas-Peran (`QUERY_DENIED`)**:
   - Sistem wajib melakukan pemeriksaan relevansi dokumen tanpa filter RBAC.
   - Jika kueri pengguna tidak menemukan dokumen yang diizinkan, TETAPI menemukan dokumen berklasifikasi lain di luar izin perannya (contoh: staf `HR` menanyakan hal yang hanya ada di dokumen `Finance`):
     - Sistem **DILARANG** membocorkan konten dokumen.
     - Sistem wajib mengembalikan status `QUERY_DENIED` beserta klasifikasi yang terhalang (`blocked_classification`).
     - Pesan respons: *"Tidak ada dokumen yang dapat diakses peran {user_role} untuk pertanyaan ini. Dokumen terkait diklasifikasikan sebagai {blocked_classification}. Hubungi Admin jika Anda memerlukan akses."*
     - Wajib dicatat ke `audit_logs` dengan aksi `QUERY_DENIED` dan status `Ditolak RBAC`.

---

## 3. Standar Keamanan & Audit Log

### 3.1 Imutabilitas Audit Log (*Append-Only*)
- Tabel `audit_logs` bersifat murni **append-only**.
- Operasi `UPDATE` dan `DELETE` pada tabel `audit_logs` **DIBLOKIR MUTLAK** menggunakan trigger PostgreSQL (`prevent_audit_log_modification`) yang me-raise exception bila ada percobaan modifikasi atau penghapusan data.

### 3.2 Rantai Hash Kriptografis (SHA-256)
- Setiap baris `audit_logs` memiliki kolom `prev_hash` dan `curr_hash`.
- Untuk baris pertama (genesis), `prev_hash` bernilai `"GENESIS"`.
- Untuk setiap baris baru:
  ```python
  curr_hash = sha256(f"{prev_hash}|{created_at_iso}|{actor_name}|{actor_role}|{action}|{detail}|{status}")
  ```
- Sediakan fungsi/endpoint untuk verifikasi rantai hash (`verify_audit_chain`) guna menjamin keutuhan dan mendeteksi jika terjadi manipulasi data di level database.

### 3.3 Aksi Wajib Catat ke `audit_logs`
Setiap kejadian penting berikut **wajib dicatat** ke `audit_logs`:
1. `LOGIN`: Saat pengguna berhasil melakukan autentikasi.
2. `LOGIN_FAILED`: Saat upaya autentikasi gagal (kredensial salah / token tidak valid).
3. `LOGOUT`: Saat pengguna mengakhiri sesi.
4. `QUERY`: Saat pengguna mengajukan pertanyaan RAG yang berhasil dijawab.
5. `QUERY_DENIED`: Saat pertanyaan pengguna ditolak karena dokumen terkait berada di luar hak akses RBAC.
6. `PROMPT_INJECTION`: Saat input kueri pengguna terdeteksi mengandung pola manipulasi prompt sistem/bypass instruksi.
7. `DOC_UPLOAD`: Saat admin mengunggah dokumen baru ke sistem.
8. `DOC_DELETE`: Saat admin menghapus dokumen dari sistem.
9. `ROLE_UPDATE`: Saat admin memperbarui izin atau peran pengguna.
10. `FEEDBACK`: Saat pengguna memberikan umpan balik (positif/negatif) pada jawaban chat.

---

## 4. Konvensi Kode & Konsistensi Implementasi

1. **Struktur Model & Schema**:
   - Seluruh model basis data ORM ditempatkan di `backend/app/models.py`.
   - Seluruh skema validasi Pydantic v2 ditempatkan di `backend/app/schemas.py`.
   - Selalu gunakan `UUID` untuk primary key entitas (kecuali `audit_logs` yang menggunakan `BIGSERIAL` urut untuk menjaga urutan rantai hash).
2. **Sanitasi Input**:
   - Sebelum kueri dikirim ke Ollama atau di-embed, jalankan pengecekan deteksi *prompt injection* (seperti `ignore previous instructions`, `system prompt`, `bypass rbac`, `act as admin`).
   - Jika terdeteksi injeksi, langsung blokir dan catat `PROMPT_INJECTION` ke `audit_logs`.
3. **Format Sitasi & Respons RAG**:
   - LLM wajib diinstruksikan menjawab berdasarkan dokumen konteks dengan sitasi bernomor inline seperti `[1]`, `[2]`.
   - Metadata sitasi harus mengembalikan `filename`, `page_number`, `section_title`, `classification`, dan `relevance_score`.
4. **Desain UI / Frontend**:
   - Antarmuka frontend di `frontend/` wajib mengikuti mockup dan panduan prototipe Figma:
     - `LoginPage`: Split layout (gelap/terang) dengan opsi form login dan SSO Keycloak.
     - `ChatPage`: Sidebar riwayat waktu (`HARI INI`, `7 HARI TERAKHIR`, `BULAN LALU`), bubble chat merah untuk user, bubble sitasi untuk asisten, umpan balik 👍/👎, dan alert penolakan RBAC kuning.
     - `AdminPage`: Dasbor kesehatan sistem, kelola dokumen, dan matriks peran/izin.
     - `AuditorPage`: Tinjau log audit (read-only), status verifikasi rantai hash, dan ekspor CSV.
