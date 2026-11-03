# IPPL Chatbot: Chatbot Cerdas & Aman

Chatbot cerdas untuk mencari dan menanyakan isi dokumen internal perusahaan dengan bahasa alami. Dibangun menggunakan arsitektur **Enterprise Retrieval-Augmented Generation (RAG)**, jawaban dilengkapi dengan sitasi inline `[1]`, `[2]` ke dokumen sumber, akses dokumen dibatasi secara ketat menggunakan **Role-Based Access Control (RBAC)**, dan setiap aktivitas tercatat dalam **Log Audit Imutabel berantai hash kriptografis SHA-256**.

Proyek ini dikerjakan sebagai tugas besar (TUBES) Rekayasa Perangkat Lunak / Konstruksi Perangkat Lunak, Program Studi Teknik Informatika, Fakultas Informatika, Universitas Telkom.

---

## 🌟 Fitur Utama

- **Tanya Jawab Dokumen Bersitasi**: Ekstraksi PDF dan DOCX dengan chunking semantik, similarity search vektor 768-dimensi via `pgvector`, dan generasi jawaban bersitasi terverifikasi `[1]`, `[2]`.
- **Keamanan & Isolasi RBAC Ketat**: 4 klasifikasi dokumen (`Public`, `HR`, `Finance`, `Confidential`) yang terisolasi per peran pengguna. Kueri di luar izin peran otomatis ditolak (`QUERY_DENIED`) tanpa membocorkan konten.
- **Deteksi Serangan Prompt Injection**: Filter otomatis sebelum LLM yang memblokir instruksi manipulasi prompt (`PROMPT_INJECTION`) dan mencatat insiden ke audit log.
- **Log Audit Imutabel & Verifikasi Kriptografis**: Rantai hash SHA-256 berkesinambungan (`prev_hash` $\to$ `curr_hash`) dengan proteksi trigger database (menolak `UPDATE` dan `DELETE`) dan endpoint verifikasi keutuhan rantai (`GET /audit/verify`).
- **Konsol Admin Komprehensif**: Dasbor kesehatan sistem real-time (latensi kueri p95, grafik 24 jam, status layanan, distribusi klasifikasi dokumen, dan kejadian keamanan), manajemen dokumen (upload & reindex), serta matriks peran & izin RBAC interaktif.
- **Konsol Auditor Khusus**: Antarmuka *read-only* untuk auditor dengan banner verifikasi integritas, filter multi-kriteria (peran, aksi, status), dan ekspor laporan CSV.

---

## 🛠️ Stack Teknologi

| Komponen | Teknologi | Keterangan |
| :--- | :--- | :--- |
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy 2.0 (Async) | Kinerja asinkron tinggi dengan `asyncpg` |
| **Database** | PostgreSQL 16 + ekstensi `pgvector` | Indeks HNSW vektor kosinus 768 dimensi |
| **Autentikasi** | Keycloak 26.0 (IdP) | Autentikasi OAuth2/OIDC & validasi token RS256 JWKS |
| **LLM & Embedding** | Ollama (`llama3.2:3b` / `llama3`), `nomic-embed-text` | Inferensi lokal aman tanpa transfer data ke luar |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons | Desain UI responsif berbasis prototipe Figma |
| **Testing** | `pytest`, `pytest-asyncio`, `httpx` | Uji unit modul, uji keamanan, dan benchmark beban p95 |

---

## 👥 Matriks Akun Pengguna & Izin Akses Dokumen

Seluruh akun dev telah dikonfigurasi di `infra/keycloak/dev-realm.json` dan otomatis disinkronkan ke basis data:

| Username | Nama Lengkap | Peran (Role) | Dokumen yang Diizinkan | Hak Istimewa | Password |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `andi` | Andi Nugroho | **Karyawan** | `Public` | Chat pengguna umum | `password123` |
| `rina` | Rina Pratama | **HR** | `Public`, `HR` | Chat divisi HR | `password123` |
| `dimas` | Dimas Fajar | **Finance** | `Public`, `Finance` | Chat divisi Keuangan | `password123` |
| `sari` | Sari Wulandari | **Manajemen** | `Public`, `HR`, `Finance`, `Confidential` | Akses seluruh dokumen | `password123` |
| `admin_sistem` | Admin Sistem | **Admin** | `Public` | Kelola Dokumen, RBAC, Dasbor | `password123` |
| `budi` | Budi Santoso | **Auditor** | *(Tidak ada)* | Tinjau Log Audit (*Read-only*) | `password123` |
| `dev` | Dev User | **Admin** | `Public` | Akun pengembangan awal | `dev` |

---

## 🏗️ Arsitektur Alur Kueri & Audit Hash Chain

```
               [ Pengguna Mengirim Pertanyaan ]
                              │
                              ▼
           ┌──────────────────────────────────────┐
           │   Deteksi Serangan Prompt Injection  │
           └──────────────────┬───────────────────┘
                              │
               Terdeteksi? ───┴─── Aman?
              ┌───────┘               └───┐
              ▼                           ▼
   [ Blokir Sebelum LLM ]       [ Buat Embedding Vektor ]
   - Status: PROMPT_INJECTION   - nomic-embed-text (768 dimensi)
   - Catat di Audit Log                   │
                                          ▼
                        ┌───────────────────────────────────┐
                        │ Similarity Search pgvector (HNSW) │
                        │  WHERE classification IN (RBAC)   │
                        └─────────────────┬─────────────────┘
                                          │
                   Dokumen Berizin? ──────┴────── Terkait Dokumen Terlarang?
                  ┌────────┘                           └────────┐
                  ▼                                             ▼
      [ Ambil Top-K Chunk ]                             [ Tolak Akses ]
      - Susun konteks relevan                           - Status: QUERY_DENIED
      - Panggil Ollama (Llama 3)                        - Klasifikasi terhalang
      - Sisipkan sitasi inline [1], [2]                 - Tanpa bocoran teks
                  │                                             │
                  └───────────────────────┬─────────────────────┘
                                          │
                                          ▼
                      ┌───────────────────────────────────────┐
                      │    Append-Only Audit Log Generator    │
                      │  curr_hash = sha256(prev_hash + data) │
                      │  Proteksi: Trigger Tolak UPDATE/DELETE│
                      └───────────────────────────────────────┘
```

---

## 🚀 Panduan Menjalankan Sistem

### 1. Prasyarat
- Docker Desktop atau Colima (dengan Docker Compose v2)
- Python 3.9+ / 3.11+ (opsional untuk menjalankan unit test langsung di host)
- Node.js 18+ (opsional untuk pengembangan frontend di host)

### 2. Menjalankan Seluruh Stack dengan Docker Compose
```bash
# 1. Inisialisasi file environment
make init

# 2. Bangun dan jalankan seluruh container di background
make up
```

Layanan akan aktif pada port:
- **Frontend Web UI**: [http://localhost:5173](http://localhost:5173)
- **Backend API & Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Keycloak Admin Console**: [http://localhost:8080](http://localhost:8080) (realm: `dev`)
- **PostgreSQL + pgvector**: `localhost:5432`

### 3. Menghentikan Layanan
```bash
make down
# Atau reset volume total:
make reset
```

---

## 🧪 Validasi & Pengujian Sistem (Aktivitas 4)

Seluruh pengujian dapat dijalankan secara instan melalui target `Makefile`:

### 1. Aktivitas 4a — Pengujian Unit per Modul
Menguji 4 modul inti: `auth` (klaim JWT & RBAC), `ingestion` (ekstraksi PDF/DOCX & chunking), `retrieval` (similarity search pgvector), dan `generation` (sitasi [1], [2], latensi, umpan balik).
```bash
make test
```

### 2. Aktivitas 4b — Uji Keamanan Otomatis
Menguji 3 domain keamanan kritis:
- **Isolasi Batas RBAC**: Memastikan user `HR` ditolak (`QUERY_DENIED`) saat menanyakan dokumen `Finance` atau `Confidential`, tanpa membocorkan konten.
- **Prompt Injection Defense**: Memastikan pola injeksi prompt diblokir sebelum LLM dan tercatat sebagai `Diblokir`.
- **Imutabilitas Log Audit**: Memvalidasi trigger database penolak `UPDATE`/`DELETE` dan deteksi manipulasi rantai hash SHA-256 (`verify_audit_chain`).
```bash
make test-security
```

### 3. Aktivitas 4c — Uji Kinerja & Beban (500 Pengguna Konkuren)
Mensimulasikan beban hingga 500 pengguna aktif simultan untuk memvalidasi pemenuhan target latensi $p95 < 5.0\text{ detik}$:
```bash
make test-perf
```

### 4. Seeding Data Awal
Menginisialisasi peran pengguna, akun pengujian, dan 7 contoh dokumen uji per klasifikasi:
```bash
make seed
```

---

## 📁 Struktur Direktori Proyek

```
ippl-chatbot/
├── backend/
│   ├── app/
│   │   ├── models.py           # Model SQLAlchemy (pgvector, RBAC, Audit Log)
│   │   ├── auth.py             # Validasi JWT Keycloak & dependency current_user
│   │   ├── routers/
│   │   │   ├── chat.py         # Router Chat, Sesi, dan Umpan Balik
│   │   │   ├── admin.py        # Router Admin (Dasbor Kesehatan, Dokumen, Peran)
│   │   │   └── audit.py        # Router Auditor (Log Audit, Verifikasi SHA-256, Ekspor CSV)
│   │   └── services/
│   │       ├── ingestion_service.py # Ekstraksi PDF/DOCX & Embedding 768-d
│   │       ├── rag_service.py       # Pipeline RAG, RBAC Filter, & Prompt Injection Guard
│   │       └── audit_service.py     # Rantai Hash SHA-256 & Verifikasi Integritas
│   ├── tests/
│   │   ├── test_4a_unit_modules.py  # Aktivitas 4a: Unit Test per Modul
│   │   └── test_4b_security.py      # Aktivitas 4b: Uji Keamanan Otomatis
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx        # Halaman Masuk Akun (Gambar 1)
│   │   │   ├── ChatPage.tsx         # Halaman Chat Utama & Sitasi (Gambar 2 & 3)
│   │   │   ├── admin/               # Halaman Admin (Dasbor, Dokumen, Peran)
│   │   │   └── auditor/             # Halaman Auditor (Log Audit & Verifikasi)
│   │   └── layouts/
├── infra/
│   ├── keycloak/dev-realm.json      # Konfigurasi Realm, 6 Peran, & Akun Prototipe
│   └── postgres/init.sql            # Ekstensi vector & Trigger Append-Only
├── scripts/
│   └── load_test_4c.py              # Aktivitas 4c: Skrip Uji Beban 500 Pengguna
├── Makefile                         # Otomasi build, up, test, seed
└── README.md
```

---

## 👥 Tim Pengembang

| Nama | Program Studi / Universitas |
| :--- | :--- |
| **Yoel Gabriel Nainggolan** | S1 Teknik Informatika, Universitas Telkom |
| **Aqsyal Raihan Jamil** | S1 Teknik Informatika, Universitas Telkom |
| **Ilham Rizal Diantama** | S1 Teknik Informatika, Universitas Telkom |
| **Dwiyana Tri Pandaya** | S1 Teknik Informatika, Universitas Telkom |
