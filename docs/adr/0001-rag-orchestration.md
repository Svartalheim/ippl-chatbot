# ADR 0001 — Orkestrasi RAG: pipeline kustom, bukan LlamaIndex

- **Status:** Diusulkan (perlu persetujuan tim)
- **Tanggal:** 2026-11-24
- **Terkait:** SKPL §2.4.2.2, FR-RAG-001..006, NFR-SEC-001/002/012

## Konteks
SKPL menetapkan LlamaIndex sebagai lapisan orkestrasi. Implementasi saat ini tidak memakai LlamaIndex: pipeline ditulis langsung di `backend/app/services/rag_service.py` dan `ingestion_service.py` (pypdf/python-docx → chunking → embedding Ollama → SQL pgvector → prompt → Ollama chat).

## Opsi
1. **Ubah SKPL** agar sesuai implementasi (pipeline kustom).
2. **Migrasi ke LlamaIndex** (`PGVectorStore` + `MetadataFilters` + `VectorStoreIndex.as_query_engine`).

## Pertimbangan
| Aspek | Pipeline kustom | LlamaIndex |
|---|---|---|
| Filter RBAC | SQL eksplisit `classification = ANY(:allowed)` sebelum top-K; mudah diaudit dan diuji (NFR-SEC-002/012) | Melalui `MetadataFilters`; perilaku pra-filter bergantung versi integrasi pgvector |
| Deteksi `QUERY_DENIED` | Kueri global top-1 terpisah, sederhana | Perlu retriever kedua / kustom |
| Log audit per chunk (NFR-SEC-016) | ID chunk tersedia langsung dari hasil SQL | Perlu callback/handler tambahan |
| Dependensi & ukuran image | Sedikit (httpx, pgvector, pypdf) | Banyak paket tambahan |
| Usaha migrasi | Tidak ada | Penulisan ulang ingestion + retrieval + pengujian ulang 4a/4b |
| Kesesuaian dokumen | Perlu revisi SKPL | Sesuai SKPL |

## Keputusan (rekomendasi)
**Opsi 1.** Pertahankan pipeline kustom dan revisi SKPL §2.4.2.2 menjadi:

> **Lapisan Orkestrasi:** Pipeline RAG kustom di dalam aplikasi FastAPI (Python): ekstraksi PDF/DOCX, chunking ±500 kata dengan overlap 100, embedding `nomic-embed-text` via Ollama, pencarian kesamaan kosinus di PostgreSQL/pgvector (indeks HNSW) dengan filter metadata klasifikasi **sebelum** pengambilan, penyusunan prompt terstruktur, dan generasi jawaban via Ollama. Pendekatan ini dipilih agar filter RBAC dan pencatatan audit per chunk dapat dikendalikan dan diverifikasi secara langsung.

## Konsekuensi
- Tim memelihara kode retrieval sendiri (sudah tercakup pengujian `test_4a`, `test_4b`, `test_5`).
- Jika kelak dibutuhkan konektor sumber (SharePoint/Confluence), loader LlamaIndex dapat dipakai **hanya** untuk tahap penyerapan tanpa mengubah jalur retrieval.
