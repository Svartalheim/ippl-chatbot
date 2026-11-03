import React, { useEffect, useState } from "react";
import {
  Check,
  Edit2,
  Plus,
  RefreshCw,
  Search,
  Users,
  X,
} from "lucide-react";
import { api } from "../../api/client";

interface RoleItem {
  id: number;
  name: string;
  description?: string;
  allowed_classifications: Array<"Public" | "HR" | "Finance" | "Confidential">;
  can_manage_docs: boolean;
  can_manage_rbac: boolean;
  can_view_audit: boolean;
  user_count: number;
}

interface UserItem {
  id: string;
  username: string;
  full_name?: string;
  email?: string;
  role_id?: number;
  is_active: boolean;
  last_login_at?: string;
  role?: {
    id: number;
    name: string;
  };
}

export const AdminRolesPage: React.FC = () => {
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [totalUsers, setTotalUsers] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  // User search & pagination
  const [userSearch, setUserSearch] = useState("");
  const [userPage, setUserPage] = useState(1);

  // Role edit modal
  const [editingRole, setEditingRole] = useState<RoleItem | null>(null);
  const [roleForm, setRoleForm] = useState<{
    allowed_classifications: Array<"Public" | "HR" | "Finance" | "Confidential">;
    can_manage_docs: boolean;
    can_view_audit: boolean;
  }>({
    allowed_classifications: [],
    can_manage_docs: false,
    can_view_audit: false,
  });
  const [isSavingRole, setIsSavingRole] = useState(false);

  // User role change state
  const [changingUserRole, setChangingUserRole] = useState<{
    userId: string;
    newRoleId: number;
  } | null>(null);

  const loadRoles = async () => {
    try {
      const data = await api.get<RoleItem[]>("/admin/roles");
      setRoles(data);
    } catch (err) {
      console.error("Gagal memuat peran:", err);
    }
  };

  const loadUsers = async () => {
    try {
      const params = new URLSearchParams();
      if (userSearch) params.append("search", userSearch);
      params.append("page", userPage.toString());
      params.append("page_size", "10");

      const res = await api.get<{
        users: UserItem[];
        total: number;
        page: number;
        total_pages: number;
      }>(`/admin/users?${params.toString()}`);
      setUsers(res.users);
      setTotalUsers(res.total);
    } catch (err) {
      console.error("Gagal memuat pengguna:", err);
    }
  };

  useEffect(() => {
    Promise.all([loadRoles(), loadUsers()]).finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    loadUsers();
  }, [userSearch, userPage]);

  const handleOpenEditRole = (role: RoleItem) => {
    setEditingRole(role);
    setRoleForm({
      allowed_classifications: [...role.allowed_classifications],
      can_manage_docs: role.can_manage_docs,
      can_view_audit: role.can_view_audit,
    });
  };

  const handleToggleClassification = (cls: "Public" | "HR" | "Finance" | "Confidential") => {
    setRoleForm((prev) => {
      const exists = prev.allowed_classifications.includes(cls);
      return {
        ...prev,
        allowed_classifications: exists
          ? prev.allowed_classifications.filter((c) => c !== cls)
          : [...prev.allowed_classifications, cls],
      };
    });
  };

  const handleSaveRole = async () => {
    if (!editingRole) return;
    setIsSavingRole(true);
    try {
      await api.put(`/admin/roles/${editingRole.id}`, roleForm);
      setEditingRole(null);
      await loadRoles();
    } catch (err: any) {
      alert("Gagal memperbarui izin peran: " + err.message);
    } finally {
      setIsSavingRole(false);
    }
  };

  const handleChangeUserRole = async (userId: string, newRoleId: number) => {
    try {
      await api.put(`/admin/users/${userId}/role`, { role_id: newRoleId });
      setChangingUserRole(null);
      await Promise.all([loadUsers(), loadRoles()]);
    } catch (err: any) {
      alert("Gagal mengubah peran pengguna: " + err.message);
    }
  };

  const getRoleBadge = (roleName: string) => {
    switch (roleName) {
      case "Admin":
        return "bg-red-50 text-red-700 border-red-200";
      case "HR":
        return "bg-blue-50 text-blue-700 border-blue-200";
      case "Finance":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "Manajemen":
        return "bg-rose-50 text-rose-700 border-rose-200";
      case "Auditor":
        return "bg-purple-50 text-purple-700 border-purple-200";
      default:
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-12 text-gray-500">
        <RefreshCw className="w-8 h-8 animate-spin text-red-600 mb-3" />
        <span className="text-sm font-medium">Memuat data peran dan pengguna...</span>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto w-full">
      {/* Header Halaman */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Peran & Izin</h1>
          <p className="text-xs text-gray-500 mt-1">
            Atur peran pengguna dan klasifikasi dokumen yang boleh diakses setiap peran (RBAC).
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => alert("Fitur undangan pengguna diarahkan ke manajemen realm Keycloak.")}
            className="flex items-center gap-1.5 px-3 py-2 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-xs font-semibold rounded-xl shadow-sm transition"
          >
            <Users className="w-3.5 h-3.5 text-gray-500" />
            <span>Undang pengguna</span>
          </button>

          <button
            onClick={() => alert("Peran sistem terintegrasi dengan Keycloak dev-realm.json.")}
            className="flex items-center gap-1.5 px-4 py-2 bg-[#C92A2A] hover:bg-[#A61E1E] text-white text-xs font-semibold rounded-xl shadow-sm transition"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Tambah peran</span>
          </button>
        </div>
      </div>

      {/* ======================================================== */}
      {/* 1. Matriks Akses Per Peran (Tabel Atas) */}
      {/* ======================================================== */}
      <div className="bg-white p-6 rounded-2xl border border-gray-200/80 shadow-sm space-y-4">
        <div>
          <h2 className="text-sm font-bold text-gray-900">Matriks akses per peran</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Klasifikasi dipakai sebagai filter metadata saat similarity search di pgvector. Perubahan berlaku pada kueri berikutnya.
          </p>
        </div>

        <div className="overflow-x-auto border-t border-gray-100 pt-3">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-gray-400 border-b border-gray-100 font-semibold uppercase text-[10px] tracking-wider">
                <th className="pb-3">Peran</th>
                <th className="pb-3 text-center">Pengguna</th>
                <th className="pb-3 text-center">Public</th>
                <th className="pb-3 text-center">HR</th>
                <th className="pb-3 text-center">Finance</th>
                <th className="pb-3 text-center">Confidential</th>
                <th className="pb-3 text-center">Kelola Dokumen</th>
                <th className="pb-3 text-center">Lihat Log Audit</th>
                <th className="pb-3 text-right">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {roles.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50/70 transition">
                  <td className="py-3.5 pr-4">
                    <div className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-gray-400"></span>
                      <div>
                        <span className="font-bold text-gray-900 block text-xs">
                          {r.name}
                        </span>
                        <span className="text-[11px] text-gray-400 block">
                          {r.description || "—"}
                        </span>
                      </div>
                    </div>
                  </td>

                  <td className="py-3.5 text-center font-bold text-gray-700">
                    {r.user_count}
                  </td>

                  {/* Public */}
                  <td className="py-3.5 text-center">
                    {r.allowed_classifications.includes("Public") ? (
                      <Check className="w-4 h-4 text-emerald-600 mx-auto" />
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>

                  {/* HR */}
                  <td className="py-3.5 text-center">
                    {r.allowed_classifications.includes("HR") ? (
                      <Check className="w-4 h-4 text-blue-600 mx-auto" />
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>

                  {/* Finance */}
                  <td className="py-3.5 text-center">
                    {r.allowed_classifications.includes("Finance") ? (
                      <Check className="w-4 h-4 text-amber-600 mx-auto" />
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>

                  {/* Confidential */}
                  <td className="py-3.5 text-center">
                    {r.allowed_classifications.includes("Confidential") ? (
                      <Check className="w-4 h-4 text-rose-600 mx-auto" />
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>

                  {/* Kelola Dokumen */}
                  <td className="py-3.5 text-center">
                    {r.can_manage_docs ? (
                      <Check className="w-4 h-4 text-emerald-600 mx-auto" />
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>

                  {/* Lihat Log Audit */}
                  <td className="py-3.5 text-center">
                    {r.can_view_audit ? (
                      <Check className="w-4 h-4 text-emerald-600 mx-auto" />
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>

                  <td className="py-3.5 text-right">
                    <button
                      onClick={() => handleOpenEditRole(r)}
                      title="Edit Izin Peran"
                      className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ======================================================== */}
      {/* 2. Tabel Pengguna (Tabel Bawah) */}
      {/* ======================================================== */}
      <div className="bg-white p-6 rounded-2xl border border-gray-200/80 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold text-gray-900">Pengguna</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              {totalUsers} pengguna tersinkron dari Keycloak
            </p>
          </div>

          <div className="relative max-w-xs w-full">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={userSearch}
              onChange={(e) => {
                setUserSearch(e.target.value);
                setUserPage(1);
              }}
              placeholder="Cari nama atau email..."
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded-xl text-gray-800 focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500"
            />
          </div>
        </div>

        <div className="overflow-x-auto border-t border-gray-100 pt-3">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-gray-400 border-b border-gray-100 font-semibold uppercase text-[10px] tracking-wider">
                <th className="pb-3">Nama</th>
                <th className="pb-3">Peran</th>
                <th className="pb-3">Status</th>
                <th className="pb-3">Login Terakhir</th>
                <th className="pb-3 text-right">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {users.map((u) => {
                const currentRoleName = u.role?.name || "Karyawan";
                const initials = (u.full_name || u.username)
                  .split(" ")
                  .map((n) => n[0])
                  .join("")
                  .slice(0, 2)
                  .toUpperCase();

                const isChanging = changingUserRole?.userId === u.id;

                return (
                  <tr key={u.id} className="hover:bg-gray-50/70 transition">
                    <td className="py-3 pr-4">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-lg bg-red-100 text-red-700 font-bold text-xs flex items-center justify-center shrink-0">
                          {initials}
                        </div>
                        <div>
                          <span className="font-bold text-gray-900 block">
                            {u.full_name || u.username}
                          </span>
                          <span className="text-[11px] text-gray-400 block">
                            {u.email || `${u.username}@perusahaan.co.id`}
                          </span>
                        </div>
                      </div>
                    </td>

                    <td className="py-3 pr-4">
                      {isChanging ? (
                        <select
                          defaultValue={u.role_id || 1}
                          onChange={(e) =>
                            handleChangeUserRole(u.id, parseInt(e.target.value))
                          }
                          className="text-xs bg-gray-50 border border-gray-300 rounded px-2 py-0.5"
                        >
                          {roles.map((r) => (
                            <option key={r.id} value={r.id}>
                              {r.name}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${getRoleBadge(
                            currentRoleName
                          )}`}
                        >
                          ● {currentRoleName}
                        </span>
                      )}
                    </td>

                    <td className="py-3 pr-4">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        ● Aktif
                      </span>
                    </td>

                    <td className="py-3 pr-4 text-gray-500 text-[11px]">
                      {u.last_login_at
                        ? new Date(u.last_login_at).toLocaleDateString("id-ID", {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "Hari ini, 09:01"}
                    </td>

                    <td className="py-3 text-right">
                      <button
                        onClick={() =>
                          setChangingUserRole(
                            isChanging
                              ? null
                              : { userId: u.id, newRoleId: u.role_id || 1 }
                          )
                        }
                        className="text-[11px] font-semibold text-gray-400 hover:text-red-600 transition"
                      >
                        {isChanging ? "Batal" : "Ubah"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal Edit Izin Peran */}
      {editingRole && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-6 border border-gray-200 text-gray-900">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-base">
                Konfigurasi Izin Peran: {editingRole.name}
              </h3>
              <button
                onClick={() => setEditingRole(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-gray-500 mb-5">
              Pilih klasifikasi dokumen yang diizinkan untuk peran ini dan hak akses sistem.
            </p>

            <div className="space-y-4 mb-6">
              <div>
                <span className="text-xs font-bold text-gray-700 block uppercase tracking-wider mb-2">
                  Akses Dokumen Berdasarkan Klasifikasi
                </span>
                <div className="grid grid-cols-2 gap-2">
                  {(["Public", "HR", "Finance", "Confidential"] as const).map((cls) => {
                    const isChecked = roleForm.allowed_classifications.includes(cls);
                    return (
                      <label
                        key={cls}
                        className={`flex items-center gap-2 p-2.5 rounded-xl border text-xs font-medium cursor-pointer transition ${
                          isChecked
                            ? "bg-red-50/50 border-red-300 text-red-950 font-bold"
                            : "bg-gray-50 border-gray-200 text-gray-600"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => handleToggleClassification(cls)}
                          className="rounded text-red-600 focus:ring-red-500"
                        />
                        <span>{cls}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div>
                <span className="text-xs font-bold text-gray-700 block uppercase tracking-wider mb-2">
                  Hak Akses Konsol Khusus
                </span>
                <div className="space-y-2">
                  <label className="flex items-center gap-2.5 p-2.5 rounded-xl border border-gray-200 text-xs font-medium cursor-pointer hover:bg-gray-50">
                    <input
                      type="checkbox"
                      checked={roleForm.can_manage_docs}
                      onChange={(e) =>
                        setRoleForm((prev) => ({
                          ...prev,
                          can_manage_docs: e.target.checked,
                        }))
                      }
                      className="rounded text-red-600 focus:ring-red-500"
                    />
                    <span>Kelola Dokumen (Upload / Delete / Reindex)</span>
                  </label>

                  <label className="flex items-center gap-2.5 p-2.5 rounded-xl border border-gray-200 text-xs font-medium cursor-pointer hover:bg-gray-50">
                    <input
                      type="checkbox"
                      checked={roleForm.can_view_audit}
                      onChange={(e) =>
                        setRoleForm((prev) => ({
                          ...prev,
                          can_view_audit: e.target.checked,
                        }))
                      }
                      className="rounded text-red-600 focus:ring-red-500"
                    />
                    <span>Lihat Log Audit (Konsol Auditor Read-Only)</span>
                  </label>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditingRole(null)}
                className="px-4 py-2 text-xs text-gray-600 hover:bg-gray-100 rounded-xl transition"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={handleSaveRole}
                disabled={isSavingRole}
                className="px-5 py-2 text-xs font-bold text-white bg-red-600 hover:bg-red-700 rounded-xl transition disabled:opacity-50"
              >
                {isSavingRole ? "Menyimpan..." : "Simpan Perubahan"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
