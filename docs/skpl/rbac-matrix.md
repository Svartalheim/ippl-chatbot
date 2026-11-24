# Matriks RBAC (NFR-SEC-005)

Sumber: `backend/app/seed.py` (peran awal), `backend/app/auth.py` (`get_user_allowed_classifications`, `require_roles`), `backend/app/routers/*.py`, `frontend/src/App.tsx`.
Perubahan matriks melalui konsol Admin tercatat sebagai `ROLE_UPDATE` di log audit.

## 1. Peran × klasifikasi dokumen (hak baca isi)

| Peran (kelas pengguna SKPL) | Public | HR | Finance | Legal | Confidential |
|---|:-:|:-:|:-:|:-:|:-:|
| Karyawan (Karyawan Umum) | ✓ | | | | |
| HR (Spesialis SDM) | ✓ | ✓ | | | |
| Finance (Analis Keuangan) | ✓ | | ✓ | | |
| Legal (Penasihat Hukum) | ✓ | | | ✓ | |
| Manajemen (CEO / direksi) | ✓ | ✓ | ✓ | ✓ | ✓ |
| Admin (Administrator Sistem) | ✓ | | | | |
| Auditor (Auditor Kepatuhan) | | | | | |

Filter ini diterapkan di level chunk (`document_chunks.classification`) sebelum konteks dikirim ke LLM, dan saat membuka dokumen sumber.

## 2. Peran × kemampuan

| Peran | Chat | Buka dokumen sumber | Kelola dokumen (`can_manage_docs`) | Kelola peran (`can_manage_rbac`) | Lihat log audit (`can_view_audit`) |
|---|:-:|:-:|:-:|:-:|:-:|
| Karyawan, HR, Finance, Legal, Manajemen | ✓ | sesuai tabel 1 | | | |
| Admin | ✓ (Public) | Public saja | ✓ | ✓ | (baca, lihat §4) |
| Auditor | ✓ (tanpa dokumen) | tidak ada | | | ✓ |

## 3. Peran × API dan halaman

| Grup endpoint | Dependensi | Peran |
|---|---|---|
| `/auth/login`, `/auth/refresh`, `/auth/logout` | publik / token opsional | semua |
| `/auth/introspect` | debug, dimatikan di produksi (`ENABLE_DEBUG_ENDPOINTS=false`) | — |
| `/chat/*` (sesi, kueri, feedback, `/chat/documents/*`) | `current_user` | semua pengguna terautentikasi; data dibatasi pemilik sesi + tabel 1 |
| `/llm/chat` (kompatibilitas lama) | `current_user` + filter RBAC | semua pengguna terautentikasi |
| `/admin/*` | `require_roles("Admin")` | Admin |
| `/audit/*` | `require_roles("Auditor", "Admin")` | Auditor, Admin |

| Halaman | `ProtectedRoute` |
|---|---|
| `/` (chat) | semua pengguna terautentikasi |
| `/admin`, `/admin/documents`, `/admin/roles` | Admin |
| `/auditor` | Auditor |

## 4. Catatan terhadap SKPL §2.3
- **Pemisahan tugas Admin:** terpenuhi untuk isi dokumen (Admin hanya Public). Admin masih dapat **membaca** log audit (`/audit/*`), sesuai §2.3 "pemantauan log", tetapi tidak dapat mengubahnya (append-only).
- **Auditor:** tidak memiliki klasifikasi apa pun, sehingga tidak dapat membaca isi dokumen; akses konfigurasi hanya baca melalui log.
- **Sumber kebenaran peran:** peran pengguna dibaca dari klaim JWT Keycloak pada setiap permintaan. Perubahan "Ubah Peran Pengguna" di konsol Admin tertimpa pada permintaan berikutnya bila peran di Keycloak berbeda (lihat temuan S5 di `docs/verification/security-review.md`).
