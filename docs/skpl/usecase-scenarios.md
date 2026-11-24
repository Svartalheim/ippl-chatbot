# Skenario Use Case (pengganti SKPL §3.2.1.1–3.2.1.10)

Selaras dengan `docs/diagrams/usecase.puml`. Setiap alur alternatif mengacu pada perilaku nyata aplikasi (kode HTTP / aksi log audit).
Aktor "Pengguna" mencakup Karyawan, Spesialis SDM (HR), Analis Keuangan, Manajemen/CEO, dan Penasihat Hukum (Legal).

---

## UC-01 Login Aplikasi

| Bagian | Isi |
|---|---|
| Aktor | Pengguna, Administrator Sistem, Auditor Kepatuhan; aktor sekunder: Keycloak |
| Deskripsi | Masuk ke sistem dengan mengotentikasi kredensial melalui Identity Provider (Keycloak). |
| Pre-kondisi | Pengguna berada di halaman login dan akunnya terdaftar di Keycloak. |
| Post-kondisi | Token akses (JWT) dan refresh token tersimpan di aplikasi; pengguna diarahkan ke halaman sesuai peran; event `LOGIN` tercatat. |

**Skenario utama**

| Aktor | Sistem |
|---|---|
| 1. Membuka aplikasi. | 2. Menampilkan formulir login (username, password). |
| 3. Mengisi username dan password, menekan **Masuk**. | 4. Meneruskan kredensial ke Keycloak (UC-02 Verifikasi Autentikasi). |
| | 5. Menerima JWT, memvalidasi tanda tangan & masa berlaku, menyinkronkan data pengguna ke basis data. |
| | 6. Mencatat `LOGIN` (Berhasil) di log audit. |
| | 7. Mengarahkan ke `/admin` (Admin), `/auditor` (Auditor), atau halaman chat (peran lain). |

**Skenario alternatif**

| Kondisi | Aktor | Sistem |
|---|---|---|
| A1. Kredensial salah | — | 4a. Keycloak menolak; sistem mencatat `LOGIN_FAILED` (Gagal), menampilkan "username atau password salah" (HTTP 401). Kembali ke langkah 3. |
| A2. Gagal berulang | — | 4b. Bila ≥ `SECURITY_ALERT_THRESHOLD` kejadian berisiko dalam `SECURITY_ALERT_WINDOW_MINUTES`, sistem mencatat `SECURITY_ALERT` dan menampilkannya di dasbor Admin. |
| A3. Keycloak tidak dapat dihubungi | — | 4c. Menampilkan pesan layanan autentikasi tidak tersedia (HTTP 503). |
| A4. Sesi pernah diakhiri Admin | — | 5a. Token lama ditolak (HTTP 401 "Sesi telah diakhiri"); pengguna harus login ulang. |

---

## UC-02 Verifikasi Autentikasi (included oleh UC-01)

| Bagian | Isi |
|---|---|
| Aktor | Keycloak (sekunder) |
| Deskripsi | Fungsi internal yang memvalidasi kredensial terhadap Keycloak, bukan terhadap kata sandi di basis data aplikasi (aplikasi tidak menyimpan kata sandi). |
| Pre-kondisi | Sistem menerima username dan password dari UC-01. |
| Post-kondisi | Status Berhasil (token diterbitkan) atau Gagal. |

| Aktor | Sistem |
|---|---|
| | 1. Mengirim permintaan `grant_type=password` ke endpoint token Keycloak. |
| | 2. Keycloak membandingkan kredensial dengan hash kata sandinya. |
| | 3a. Valid: mengembalikan access token (JWT berisi ID unik & peran) + refresh token ke UC-01. |
| | 3b. Tidak valid: mengembalikan `invalid_grant` ke UC-01 (lanjut ke A1). |

---

## UC-03 Logout

| Bagian | Isi |
|---|---|
| Aktor | Pengguna, Administrator Sistem, Auditor Kepatuhan |
| Pre-kondisi | Pengguna dalam sesi aktif. |
| Post-kondisi | Refresh token dicabut di Keycloak, token dihapus dari peramban, event `LOGOUT` tercatat, pengguna di halaman login. |

| Aktor | Sistem |
|---|---|
| 1. Memilih **Logout**. | 2. Menampilkan dialog konfirmasi. |
| 3. Mengonfirmasi. | 4. Mengirim refresh token ke `/auth/logout`; Keycloak mencabut sesi. |
| | 5. Mencatat `LOGOUT`, menghapus token, mengarahkan ke `/login`. |

| Kondisi | Sistem |
|---|---|
| A1. Membatalkan dialog | Tetap di halaman saat ini. |
| A2. Keycloak tidak dapat dihubungi | Token lokal tetap dihapus dan `LOGOUT` tetap dicatat; refresh token kedaluwarsa sesuai umurnya. |

---

## UC-04 Mengajukan Pertanyaan

| Bagian | Isi |
|---|---|
| Aktor | Pengguna; aktor sekunder: Ollama (LLM & embedding) |
| Include | UC-05 Validasi Token JWT, UC-06 Filter Akses RBAC, UC-07 Catat Log Audit |
| Pre-kondisi | Pengguna sudah login dan berada di antarmuka chat. |
| Post-kondisi | Jawaban (dengan sitasi bila ada) tampil; pertanyaan & jawaban tersimpan di riwayat; event `QUERY` / `QUERY_DENIED` / `PROMPT_INJECTION` tercatat berisi teks kueri (PII disamarkan) dan ID chunk yang diambil. |

| Aktor | Sistem |
|---|---|
| 1. Mengetik pertanyaan. | |
| 2. Menekan **Kirim** / Enter. | 3. Memvalidasi JWT dan menyimpan pesan pengguna. |
| | 4. Memeriksa pola prompt injection. |
| | 5. Membuat embedding kueri, mencari top-K chunk di pgvector **dengan** filter klasifikasi peran. |
| | 6. Menyusun prompt terstruktur (tag `<konteks_dokumen>` dan `<pertanyaan>`), mengirim ke LLM. |
| | 7. Menampilkan jawaban dengan sitasi `[1]`, `[2]` dan kartu sumber. |
| | 8. Menyimpan jawaban ke riwayat dan mencatat `QUERY` di log audit. |

| Kondisi | Sistem |
|---|---|
| A1. Pola prompt injection | 4a. Kueri diblokir sebelum mencapai LLM, `PROMPT_INJECTION` (Diblokir) dicatat, pesan penolakan ditampilkan; pemeriksaan `SECURITY_ALERT` dijalankan. |
| A2. Kueri > `MAX_QUERY_CHARS` | 3a. Kueri dipotong (bukan ditolak), jawaban diawali catatan pemotongan. |
| A3. Sapaan / pertanyaan daftar dokumen | 5a. Dijawab langsung tanpa LLM (daftar dokumen hanya yang diizinkan peran). |
| A4. Jawaban hanya ada di dokumen di luar hak akses | 5b. `QUERY_DENIED` (Ditolak RBAC) dicatat; pesan "tidak memiliki akses" ditampilkan tanpa isi dokumen. |
| A5. Tidak ada dokumen relevan | 5c. Menampilkan "Informasi tidak ditemukan dalam dokumen yang dapat Anda akses." |
| A6. Layanan embedding / LLM / vector DB gagal | 5d/6a. Menampilkan "layanan AI sedang tidak tersedia" tanpa detail teknis; `QUERY` (Gagal) dicatat. |
| A7. Token kedaluwarsa | 3a. Frontend memperbarui token via `/auth/refresh`; bila gagal, arahkan ke login. |

---

## UC-08 Lihat Sitasi & Dokumen Sumber (extend UC-04)

| Bagian | Isi |
|---|---|
| Aktor | Pengguna |
| Pre-kondisi | Jawaban dengan minimal satu sitasi tampil. |
| Post-kondisi | Isi dokumen sumber ditampilkan; `DOC_VIEW` tercatat. |

| Aktor | Sistem |
|---|---|
| 1. Mengklik kartu sumber `[n]`. | 2. Memeriksa klasifikasi dokumen terhadap hak baca peran. |
| | 3. Menampilkan PDF asli atau teks per bagian; mencatat `DOC_VIEW` (Berhasil). |
| 4. Opsional: **Unduh**. | 5. Mengirim file asli. |

| Kondisi | Sistem |
|---|---|
| A1. Klasifikasi di luar hak peran (mis. klasifikasi dokumen diubah setelah jawaban dibuat) | 2a. HTTP 403, `DOC_VIEW` (Ditolak RBAC) dicatat, pesan hak akses ditampilkan. |
| A2. File asli tidak tersimpan | 3a. Hanya pratinjau teks yang ditampilkan. |

---

## UC-09 Beri Feedback Jawaban (extend UC-04)

| Aktor | Sistem |
|---|---|
| 1. Menekan jempol atas / bawah pada jawaban. | 2. Memastikan pesan adalah jawaban asisten di sesi milik pengguna. |
| | 3. Menyimpan atau memperbarui feedback; mencatat `FEEDBACK`; menandai ikon aktif. |

| Kondisi | Sistem |
|---|---|
| A1. Pesan bukan milik pengguna / bukan jawaban asisten | HTTP 404, tidak ada yang disimpan. |
| A2. Feedback sudah ada | Nilai diperbarui (bukan duplikat). |

---

## UC-10 Kelola Riwayat Percakapan

| Bagian | Isi |
|---|---|
| Aktor | Pengguna |
| Pre-kondisi | Pengguna sudah login. |
| Post-kondisi | Daftar sesi dan isi sesi terpilih ditampilkan; sesi baru dibuat / sesi dihapus / sesi diekspor sesuai pilihan. |

| Aktor | Sistem |
|---|---|
| 1. Membuka halaman chat. | 2. Menampilkan daftar sesi milik pengguna (terbaru di atas). |
| 3. Memilih satu sesi. | 4. Menampilkan seluruh pesan beserta sitasi dan status feedback. |
| 5. Opsional: **Percakapan baru**, **Hapus**, atau **Ekspor**. | 6. Membuat sesi / menghapus sesi beserta pesannya (log audit tidak terhapus) / mengunduh Markdown. |

| Kondisi | Sistem |
|---|---|
| A1. Belum ada riwayat | Menampilkan "Belum ada percakapan." |
| A2. Sesi milik pengguna lain (ID dimanipulasi) | HTTP 404. |
| A3. Batal menghapus | Tidak ada perubahan. |

---

## UC-11 Kelola Peran & Izin (+ UC-11a Ubah Peran Pengguna, UC-15 Akhiri Sesi Pengguna)

| Bagian | Isi |
|---|---|
| Aktor | Administrator Sistem |
| Pre-kondisi | Login sebagai Admin. |
| Post-kondisi | Matriks peran × klasifikasi diperbarui; `ROLE_UPDATE` / `SESSION_TERMINATE` tercatat. |

| Aktor | Sistem |
|---|---|
| 1. Membuka **Kelola Peran & Izin**. | 2. Menampilkan matriks peran × klasifikasi (Public, HR, Finance, Legal, Confidential) + jumlah pengguna, dan daftar pengguna. |
| 3. Menambah peran atau mengubah klasifikasi/izin suatu peran. | 4. Memvalidasi, menyimpan, mencatat `ROLE_UPDATE`. |
| 5. (UC-11a) Memilih pengguna dan peran baru. | 6. Menyimpan, mencatat `ROLE_UPDATE`. |
| 7. (UC-15) Memilih **Akhiri Sesi** pada pengguna. | 8. Logout semua sesi di Keycloak, menolak token lama, mencatat `SESSION_TERMINATE`. |

| Kondisi | Sistem |
|---|---|
| A1. Nama peran sudah ada / data tidak valid | HTTP 400, pesan validasi. |
| A2. Mengakhiri sesi diri sendiri | HTTP 400, arahkan memakai Logout. |
| A3. Keycloak tidak dapat dihubungi saat UC-15 | Token lama tetap ditolak backend; pesan peringatan ditampilkan. |

---

## UC-12 Kelola Dokumen (+ Unggah, Hapus, Ubah Klasifikasi, Legal Hold, Indeks Ulang)

| Bagian | Isi |
|---|---|
| Aktor | Administrator Sistem; aktor sekunder: Ollama (embedding) |
| Pre-kondisi | Login sebagai Admin. |
| Post-kondisi | Basis pengetahuan diperbarui dan terindeks; aksi tercatat (`DOC_UPLOAD`, `DOC_DELETE`, `DOC_RECLASSIFY`, `LEGAL_HOLD`, `DOC_REINDEX`). |

| Aktor | Sistem |
|---|---|
| 1. Membuka **Kelola Dokumen**. | 2. Menampilkan daftar dokumen, klasifikasi, status indeks, ringkasan per klasifikasi. |
| 3. Memilih **Unggah**, memilih file PDF/DOCX dan klasifikasi. | 4. Memvalidasi nama file, ekstensi, ukuran, tanda tangan file, dan duplikat (SHA-256). |
| | 5. Menyimpan file, mengekstrak teks, membuat chunk & embedding, menandai klasifikasi tiap chunk, status **Terindeks**; mencatat `DOC_UPLOAD`. |
| 6. Opsional: ubah klasifikasi / aktifkan legal hold / hapus / indeks ulang. | 7. Menjalankan aksi dan mencatat log audit yang sesuai. |

| Kondisi | Sistem |
|---|---|
| A1. Format bukan PDF/DOCX, file `.doc` lama, file kosong, > 20 MB, atau isi tidak sesuai ekstensi | HTTP 400 dengan alasan; `DOC_UPLOAD` (Gagal) dicatat. |
| A2. Isi file sama dengan dokumen yang sudah ada | HTTP 409, menyebut nama dokumen yang sama. |
| A3. Tidak ada teks yang dapat diekstrak (PDF hasil scan) / file rusak | Status **Gagal** + pesan galat; dokumen tidak dipakai menjawab. |
| A4. Menghapus dokumen dengan legal hold | HTTP 423, tombol hapus dinonaktifkan. |
| A5. Admin membuka dokumen di luar hak bacanya | HTTP 403 dan `DOC_VIEW` (Ditolak RBAC) — pemisahan tugas. |

---

## UC-13 Lihat Dasbor Kesehatan Sistem

| Aktor | Sistem |
|---|---|
| 1. Membuka dasbor Admin. | 2. Mengumpulkan metrik: jumlah kueri hari ini, latensi p95 per jam, pengguna aktif, rasio feedback positif, status layanan (DB, Ollama, Keycloak), dokumen per klasifikasi, kejadian keamanan 24 jam (termasuk `SECURITY_ALERT`). |
| 3. Membuka ulang / memuat ulang halaman. | 4. Mengambil metrik terbaru (jendela tetap: hari ini dan 24 jam terakhir). |

| Kondisi | Sistem |
|---|---|
| A1. Salah satu layanan mati | Status layanan ditandai merah; metrik lain tetap tampil. |
| A2. Ada `SECURITY_ALERT` | Banner merah dengan jumlah peringatan dan arahan ke log audit. |

---

## UC-14 Tinjau Log Audit (+ Verifikasi Rantai Hash, Ekspor CSV)

| Bagian | Isi |
|---|---|
| Aktor | Auditor Kepatuhan (Admin juga dapat membaca) |
| Pre-kondisi | Login dengan peran Auditor. |
| Post-kondisi | Log ditampilkan sesuai filter; hasil verifikasi rantai / file CSV tersedia. |

| Aktor | Sistem |
|---|---|
| 1. Membuka **Tinjau Log Audit**. | 2. Menampilkan log terbaru (paginasi) dan status rantai hash. |
| 3. Mengatur filter: kata kunci, rentang tanggal, peran, jenis aksi, status. | 4. Mengambil dan menampilkan log sesuai filter (hanya baca). |
| 5. Opsional: **Verifikasi Rantai**. | 6. Menghitung ulang SHA-256 setiap baris berurutan dan menampilkan hasilnya. |
| 7. Opsional: **Ekspor CSV**. | 8. Mengunduh log sesuai filter. |

| Kondisi | Sistem |
|---|---|
| A1. Filter tanpa hasil | Menampilkan tabel kosong dengan keterangan. |
| A2. Rantai rusak | Menampilkan ID entri pertama yang rusak. |
| A3. Log lama sudah diarsipkan (retensi) | Rantai diverifikasi dari hash jangkar yang tercatat di entri `AUDIT_ARCHIVE`. |
