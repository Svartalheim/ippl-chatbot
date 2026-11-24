# Laporan Pengujian (VER-01)

Tanggal: 2026-11-24 · Lingkungan: Python 3.10, dependensi `backend/requirements.txt`, tanpa stack Docker.

| Rangkaian | Perintah | Hasil |
|---|---|---|
| Unit per modul (4a) | `make test` | lulus |
| Keamanan (4b, mock) | `make test-security` (bagian non-integrasi) | lulus |
| Celah SKPL (5, baru) | `pytest backend/tests/test_5_skpl_gaps.py` | lulus |
| **Total non-integrasi** | `make test-all` | **84 lulus**, 5 dilewati (`integration`) |
| Integrasi DB (4b) | `make test-db` (butuh `make up`) | belum dijalankan di lingkungan ini |
| Kinerja (4c) | `make test-perf` (butuh `make up`) | belum dijalankan (VER-03) |
| Frontend type-check | `npx tsc --noEmit` | lulus |
| Frontend build | `npm run build` | belum dijalankan di lingkungan ini |
| Profil produksi | `make up-prod` | belum dijalankan (butuh Docker) |

## Cakupan uji baru (`test_5_skpl_gaps.py`)
- Penyamaran PII: email, NIK, telepon, NPWP, nomor rekening; teks biasa tidak berubah.
- Validasi unggahan: PDF/DOCX valid, tanda tangan palsu, `.doc` lama, ekstensi asing, file kosong, file > batas, path traversal pada nama file, SHA-256.
- Log audit kueri: teks lengkap (bukan 40 karakter), PII disamarkan, batas panjang, ID chunk.
- Pembatas prompt tidak dapat ditutup paksa oleh input.
- Pemotongan kueri panjang (FR-QUERY-005).
- Peringatan keamanan: ambang tercapai, di bawah ambang, tidak berulang dalam satu jendela, aksi tidak berisiko diabaikan, kegagalan DB tidak menggagalkan permintaan.
- Pencabutan sesi: token lama ditolak, token baru diterima, pengguna nonaktif ditolak.
- Rantai audit setelah retensi: valid dengan jangkar `AUDIT_ARCHIVE`, rusak tanpa jangkar.

## Langkah verifikasi manual setelah `make up`
1. `make test-db` dan `make test-perf CONCURRENCY=50 REQUESTS=200`; catat p95 di `docs/verification/load-test.md`.
2. Login `andi` (Karyawan) → tanya kebijakan kerja hybrid → klik kartu sumber → dokumen terbuka.
3. Login `rina` (HR) → buka ID dokumen Finance via `/chat/documents/{id}/preview` → 403 + `DOC_VIEW` Ditolak RBAC di log.
4. Admin → unggah file `.exe` berganti nama `.pdf` → 400; unggah PDF yang sama dua kali → 409; aktifkan legal hold → hapus ditolak.
5. Kirim 5 kueri prompt injection dalam 10 menit → banner `SECURITY_ALERT` di dasbor; Admin → **Akhiri Sesi** → token pengguna lama mendapat 401.
6. Auditor → Verifikasi Rantai → valid.
