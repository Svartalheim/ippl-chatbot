# IPPL Chatbot: Chatbot Cerdas & Aman

Chatbot untuk mencari dan menanyakan isi dokumen internal perusahaan dengan bahasa alami. Jawaban dibuat dari dokumen yang diambil lewat pola Retrieval-Augmented Generation (RAG), disertai sitasi ke dokumen sumber, dan akses ke tiap dokumen dibatasi sesuai peran pengguna.

Proyek ini dikerjakan sebagai tugas besar (TUBES) Program Studi Teknik Informatika, Fakultas Informatika, Universitas Telkom.

## Fitur Utama

- Tanya jawab dalam bahasa alami atas dokumen internal.
- Jawaban disertai sitasi yang dapat ditelusuri ke dokumen sumber.
- Pembatasan akses berdasarkan peran (Role-Based Access Control) pada setiap kueri.
- Riwayat percakapan dan umpan balik atas kualitas jawaban.
- Halaman admin untuk mengelola peran, izin, dan dokumen, serta dasbor kesehatan sistem.
- Log audit yang dapat ditinjau auditor secara read-only.

## Teknologi

| Lapisan | Tool |
| --- | --- |
| Database | PostgreSQL + ekstensi pgvector |
| Backend | Python, FastAPI, LlamaIndex |
| LLM | Llama 3 melalui Ollama (self-hosted) |
| Autentikasi | Keycloak (JWT) |
| Frontend | React.js + TypeScript |
| Desain UI | Figma |
| Lingkungan dev | Docker Compose, VS Code |

## Tim

| Nama |
| --- |
| Yoel Gabriel Nainggolan |
| Aqsyal Raihan Jamil |
| Ilham Rizal Diantama |
| Dwiyana Tri Pandaya |

## Rencana Konstruksi

Pengerjaan dijadwalkan 6 minggu dalam empat kelompok aktivitas: pembuatan database, antarmuka pengguna, kode program, dan pengujian.

## Status

Dalam tahap perencanaan dan pengembangan awal.
