# Daftar Koreksi untuk Dokumen SKPL (Word)

Tempel perubahan berikut ke file SKPL. Nomor bagian mengikuti nomor halaman dokumen asli.

## K1. Satukan daftar kebutuhan (masalah D1)
§3.1.1/§3.1.2 dan Lampiran A memakai ID yang sama untuk kebutuhan berbeda. **Gunakan Lampiran A sebagai satu-satunya daftar** dan ganti tabel §3.1.1 dan §3.1.2 dengan salinan Lampiran A (kolom: No, Kode, Deskripsi, Prioritas). Contoh konflik yang hilang setelah penyatuan:

| ID | §3.1 lama | Lampiran A (dipakai) |
|---|---|---|
| FR-AUTH-002 | Input username & password | Menerima JWT berisi ID unik & peran |
| FR-QUERY-003 | Feedback jempol | Sanitasi input (prompt injection) |
| FR-ADMIN-003 | Admin tambah/hapus dokumen | Auditor melihat log (read-only) |
| NFR-SEC-001..009 | 9 butir | NFR-SEC-001..018 |

Tambahkan kebutuhan yang dipakai sistem namun belum tercatat:

| ID baru | Deskripsi | Prioritas |
|---|---|---|
| FR-ADMIN-005 | Administrator dapat mengunggah, mengubah klasifikasi, dan menghapus dokumen sumber basis pengetahuan. | Must-have |
| FR-ADMIN-006 | Administrator dapat menandai dokumen dengan *legal hold* sehingga tidak dapat dihapus. | Could-have |
| FR-ADMIN-007 | Administrator dapat mengakhiri seluruh sesi aktif seorang pengguna. | Should-have |
| FR-QUERY-006 | Pengguna dapat menghapus dan mengekspor riwayat percakapannya. | Could-have |
| FR-RESP-005 | Pengguna dapat membuka dokumen sumber sitasi, dengan hak baca mengikuti matriks RBAC. | Must-have |

## K2. Ruang lingkup (masalah D2) — §1.2
Ubah butir Out-of-Scope pertama menjadi:
> **Manajemen Konten Dokumen Sumber:** Sistem tidak menyunting isi dokumen. Administrator hanya dapat menambah, mengklasifikasi ulang, atau menghapus dokumen **di basis pengetahuan chatbot**; repositori sumber (mis. SharePoint) tetap dikelola tim IT.

Ubah butir In-Scope "Penyerapan Dokumen Aman" menjadi:
> Penyerapan dokumen PDF/DOCX yang diunggah Administrator, dengan validasi format, ukuran, tanda tangan file, dan checksum SHA-256. Integrasi langsung dengan SharePoint/Confluence menjadi pengembangan lanjutan.

## K3. Kelas pengguna (masalah D3) — §2.3
Tambahkan kolom "Peran di sistem": CEO → `Manajemen` (Public, HR, Finance, Legal, Confidential); Karyawan Umum → `Karyawan`; Spesialis SDM → `HR`; Analis Keuangan → `Finance`; Penasihat Hukum → `Legal` (+ legal hold); Administrator Sistem → `Admin` (hanya dokumen Public); Auditor Kepatuhan → `Auditor` (tanpa akses isi dokumen). Rujuk `docs/skpl/rbac-matrix.md`.

## K4. Autentikasi (masalah D5) — §3.2.1.3
Ganti skenario Verifikasi Autentikasi dengan versi di `docs/skpl/usecase-scenarios.md` (UC-02): kredensial divalidasi oleh Keycloak; aplikasi tidak menyimpan kata sandi.

## K5. Skenario use case (masalah D4)
Ganti §3.2.1.1–3.2.1.10 dengan `docs/skpl/usecase-scenarios.md` (alur utama lengkap + alur alternatif).

## K6. Diagram (masalah D6–D8)
| Bagian SKPL | Ganti dengan |
|---|---|
| §3.2.1 Use Case Diagram | `docs/diagrams/usecase.png` |
| §3.2.2 Class Diagram | `docs/diagrams/class-domain.png` (+ `class-implementation.png` sebagai lampiran) |
| §3.2.3.1 Activity Pengguna | `docs/diagrams/activity-query.png` |
| §3.2.3.2 Activity Admin Dokumen | `docs/diagrams/activity-kelola-dokumen.png` |
| §3.2.3.3 Activity Auditor | `docs/diagrams/activity-audit.png` |
| Bagian baru §3.2.3.4–6 | `activity-login-logout.png`, `activity-kelola-peran.png`, `activity-feedback.png` |
| Bagian baru §3.2.4 Sequence Diagram | `seq-login.png`, `seq-query-rag.png`, `seq-upload-document.png`, `seq-audit-verify.png` |
| Bagian baru §3.2.5 ERD | `erd.png` |
| Bagian baru §2.4.3 Deployment | `deployment.png` (halaman 1: saat ini, halaman 2: target produksi) |

## K7. Lingkungan operasi (masalah D9) — §2.4
- §2.4.1: "HTTPS 1.3" → "HTTPS dengan TLS 1.3 (reverse proxy nginx pada profil produksi)".
- §2.2: "artificial intellegent" → "kecerdasan buatan (artificial intelligence)".
- §2.4.2.2 Lapisan Orkestrasi: ganti teks LlamaIndex sesuai `docs/adr/0001-rag-orchestration.md` (pipeline RAG kustom FastAPI + SQL pgvector).
- §2.4.2.3: model saat ini `llama3.2:3b` (keluarga Llama 3) dan embedding `nomic-embed-text` (768 dimensi).

## K8. Hasil survei (masalah D10)
Tambahkan paragraf penelusuran:
- Riwayat percakapan, ekspor riwayat chat, pembatasan akses per jabatan, audit trail, perlindungan dokumen sensitif → **dalam lingkup** (FR-QUERY-002, FR-QUERY-006, NFR-SEC-001..018).
- Filter pencarian (tanggal, kategori, jenis file, pembuat) dan notifikasi/reminder dokumen → **di luar lingkup rilis ini** (pengembangan lanjutan).

## K9. Daftar periksa kualitas (masalah D11) — Lampiran A Tabel 2
Ubah klaim "✓ semua" menjadi penilaian jujur, dan tambahkan cara verifikasi:

| Kebutuhan | Masalah | Perbaikan rumusan |
|---|---|---|
| NFR-USA-001 | Tidak ada metode ukur | "≥ 80% dari 5 penguji baru menyelesaikan 3 tugas inti dalam ≤ 10 menit tanpa bantuan (lihat `docs/verification/usability-test.md`)." |
| NFR-SEC-008 | CMEK bergantung penyedia cloud | "Pada penerapan cloud, kunci enkripsi basis data dikelola di KMS milik perusahaan." Prioritas tetap Should-have. |
| NFR-REL-001 | 99,9% tidak dapat diuji di lingkungan pengembangan | "Diverifikasi melalui pemantauan uptime 30 hari pada lingkungan produksi." |
