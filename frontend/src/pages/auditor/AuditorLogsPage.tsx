import React, { useEffect, useState } from "react";
import {
  Download,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import { api, BASE_URL } from "../../api/client";

interface AuditLogItem {
  id: number;
  created_at: string;
  actor_user_id?: string | null;
  actor_name: string;
  actor_role: string;
  ip_address?: string | null;
  action: string;
  detail?: string | null;
  status: "Berhasil" | "Ditolak RBAC" | "Diblokir" | "Gagal";
  prev_hash: string;
  curr_hash: string;
}

interface AuditLogsResponse {
  logs: AuditLogItem[];
  total: number;
  page: number;
  total_pages: number;
}

interface VerificationResult {
  verified: boolean;
  total_entries: number;
  checked_at: string;
  broken_at_id?: number | null;
}

export const AuditorLogsPage: React.FC = () => {
  const [data, setData] = useState<AuditLogsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("Semua");
  const [actionFilter, setActionFilter] = useState("Semua");
  const [statusFilter, setStatusFilter] = useState("Semua");
  const [page, setPage] = useState(1);

  // Verification
  const [verification, setVerification] = useState<VerificationResult | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);

  const loadAuditLogs = async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.append("search", search);
      if (roleFilter !== "Semua") params.append("role", roleFilter);
      if (actionFilter !== "Semua") params.append("action", actionFilter);
      if (statusFilter !== "Semua") params.append("status", statusFilter);
      params.append("page", page.toString());
      params.append("page_size", "10");

      const res = await api.get<AuditLogsResponse>(`/audit/logs?${params.toString()}`);
      setData(res);
    } catch (err) {
      console.error("Gagal memuat log audit:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyChain = async () => {
    setIsVerifying(true);
    try {
      const res = await api.get<VerificationResult>("/audit/verify");
      setVerification(res);
    } catch (err) {
      console.error("Gagal memverifikasi rantai hash:", err);
    } finally {
      setIsVerifying(false);
    }
  };

  useEffect(() => {
    loadAuditLogs();
  }, [search, roleFilter, actionFilter, statusFilter, page]);

  useEffect(() => {
    handleVerifyChain();
  }, []);

  const getRoleBadge = (role: string) => {
    switch (role) {
      case "HR":
        return "bg-blue-50 text-blue-700 border-blue-200";
      case "Finance":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "Admin":
        return "bg-red-50 text-red-700 border-red-200";
      case "Auditor":
        return "bg-purple-50 text-purple-700 border-purple-200";
      case "Manajemen":
        return "bg-rose-50 text-rose-700 border-rose-200";
      default:
        return "bg-gray-100 text-gray-700 border-gray-200";
    }
  };

  const getResultBadge = (st: string) => {
    switch (st) {
      case "Berhasil":
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
      case "Ditolak RBAC":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "Diblokir":
        return "bg-rose-50 text-rose-700 border-rose-200";
      case "Gagal":
        return "bg-red-50 text-red-700 border-red-200";
      default:
        return "bg-gray-100 text-gray-700 border-gray-200";
    }
  };

  const getActionBadge = (action: string) => {
    switch (action) {
      case "QUERY":
        return "bg-gray-100 text-gray-800 font-semibold";
      case "QUERY_DENIED":
        return "bg-amber-100 text-amber-900 font-bold";
      case "PROMPT_INJECTION":
        return "bg-red-100 text-red-900 font-extrabold";
      case "DOC_UPLOAD":
        return "bg-blue-100 text-blue-900 font-semibold";
      case "ROLE_UPDATE":
        return "bg-purple-100 text-purple-900 font-semibold";
      case "LOGIN":
        return "bg-emerald-100 text-emerald-900 font-semibold";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto w-full">
      {/* Header Halaman */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Log Audit</h1>
            <span className="px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 text-[10px] font-bold border border-purple-200">
              Hanya baca
            </span>
          </div>
          <p className="text-xs text-gray-500">
            Catatan aktivitas append-only — entri tidak dapat diubah atau dihapus oleh peran mana pun.
          </p>
        </div>

        <a
          href={`${BASE_URL}/audit/export-csv`}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 hover:bg-gray-50 text-gray-800 text-xs font-semibold rounded-xl shadow-sm transition"
        >
          <Download className="w-4 h-4 text-gray-600" />
          <span>Ekspor CSV</span>
        </a>
      </div>

      {/* Banner Hijau: Integritas Log Terverifikasi */}
      <div className="bg-emerald-50/70 border border-emerald-200 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <span className="text-sm font-bold text-emerald-900 block">
              Integritas log terverifikasi
            </span>
            <span className="text-xs text-emerald-700">
              Rantai hash utuh untuk{" "}
              <strong>{verification?.total_entries ?? data?.total ?? 0} entri</strong> ·
              pemeriksaan terakhir{" "}
              {verification?.checked_at
                ? new Date(verification.checked_at).toLocaleTimeString("id-ID", {
                    hour: "2-digit",
                    minute: "2-digit",
                  }) + " WIB"
                : "Baru saja"}
            </span>
          </div>
        </div>

        <button
          onClick={handleVerifyChain}
          disabled={isVerifying}
          className="px-3.5 py-1.5 bg-white border border-emerald-300 hover:bg-emerald-100/50 text-emerald-800 text-xs font-semibold rounded-xl shadow-xs transition disabled:opacity-50 flex items-center gap-1.5 shrink-0"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isVerifying ? "animate-spin" : ""}`} />
          <span>{isVerifying ? "Memverifikasi..." : "Verifikasi ulang"}</span>
        </button>
      </div>

      {/* Baris Filter */}
      <div className="bg-white p-4 rounded-2xl border border-gray-200/80 shadow-sm space-y-3">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          {/* Search Box */}
          <div className="relative flex-1 max-w-sm">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Cari pengguna, aksi, atau detail..."
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded-xl text-gray-800 focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
            />
          </div>

          <div className="flex items-center gap-2 flex-wrap text-xs">
            {/* Filter Peran */}
            <div className="flex items-center gap-1 bg-gray-50 border border-gray-200 rounded-xl px-2.5 py-1">
              <span className="text-gray-400">Peran:</span>
              <select
                value={roleFilter}
                onChange={(e) => {
                  setRoleFilter(e.target.value);
                  setPage(1);
                }}
                className="bg-transparent text-gray-700 font-semibold focus:outline-none"
              >
                <option value="Semua">Semua</option>
                <option value="HR">HR</option>
                <option value="Finance">Finance</option>
                <option value="Admin">Admin</option>
                <option value="Auditor">Auditor</option>
                <option value="Karyawan">Karyawan</option>
                <option value="Manajemen">Manajemen</option>
              </select>
            </div>

            {/* Filter Aksi */}
            <div className="flex items-center gap-1 bg-gray-50 border border-gray-200 rounded-xl px-2.5 py-1">
              <span className="text-gray-400">Aksi:</span>
              <select
                value={actionFilter}
                onChange={(e) => {
                  setActionFilter(e.target.value);
                  setPage(1);
                }}
                className="bg-transparent text-gray-700 font-semibold focus:outline-none"
              >
                <option value="Semua">Semua</option>
                <option value="QUERY">QUERY</option>
                <option value="QUERY_DENIED">QUERY_DENIED</option>
                <option value="PROMPT_INJECTION">PROMPT_INJECTION</option>
                <option value="DOC_UPLOAD">DOC_UPLOAD</option>
                <option value="ROLE_UPDATE">ROLE_UPDATE</option>
                <option value="LOGIN">LOGIN</option>
                <option value="FEEDBACK">FEEDBACK</option>
              </select>
            </div>

            {/* Filter Status */}
            <div className="flex items-center gap-1 bg-gray-50 border border-gray-200 rounded-xl px-2.5 py-1">
              <span className="text-gray-400">Hasil:</span>
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="bg-transparent text-gray-700 font-semibold focus:outline-none"
              >
                <option value="Semua">Semua</option>
                <option value="Berhasil">Berhasil</option>
                <option value="Ditolak RBAC">Ditolak RBAC</option>
                <option value="Diblokir">Diblokir</option>
                <option value="Gagal">Gagal</option>
              </select>
            </div>

            <div className="text-gray-400 font-mono text-[11px] pl-2">
              {data?.total ?? 0} entri
            </div>
          </div>
        </div>

        {/* Tabel Log Audit */}
        <div className="overflow-x-auto border-t border-gray-100 pt-3">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-gray-400 border-b border-gray-100 font-semibold uppercase text-[10px] tracking-wider">
                <th className="pb-3">Waktu</th>
                <th className="pb-3">Pengguna</th>
                <th className="pb-3">Peran</th>
                <th className="pb-3">Aksi</th>
                <th className="pb-3">Detail</th>
                <th className="pb-3">Hasil</th>
                <th className="pb-3 text-right">Hash</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-gray-400">
                    Memuat log audit...
                  </td>
                </tr>
              ) : !data || data.logs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-gray-400">
                    Tidak ada entri log audit yang sesuai.
                  </td>
                </tr>
              ) : (
                data.logs.map((log) => {
                  const initials = (log.actor_name || "U")
                    .split(" ")
                    .map((n) => n[0])
                    .join("")
                    .slice(0, 2)
                    .toUpperCase();

                  const dt = new Date(log.created_at);
                  const timeStr = dt.toLocaleTimeString("id-ID", {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  });
                  const dateStr = dt.toLocaleDateString("id-ID", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  });

                  return (
                    <tr key={log.id} className="hover:bg-gray-50/70 transition">
                      <td className="py-3 pr-4 font-mono text-[11px] text-gray-600">
                        <span className="font-bold text-gray-900 block">{timeStr}</span>
                        <span className="text-[10px] text-gray-400">{dateStr}</span>
                      </td>

                      <td className="py-3 pr-4">
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 rounded bg-purple-100 text-purple-700 font-bold text-[10px] flex items-center justify-center shrink-0">
                            {initials}
                          </div>
                          <span className="font-semibold text-gray-900 truncate max-w-[130px]">
                            {log.actor_name}
                          </span>
                        </div>
                      </td>

                      <td className="py-3 pr-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${getRoleBadge(
                            log.actor_role
                          )}`}
                        >
                          ● {log.actor_role}
                        </span>
                      </td>

                      <td className="py-3 pr-4">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono ${getActionBadge(
                            log.action
                          )}`}
                        >
                          {log.action}
                        </span>
                      </td>

                      <td className="py-3 pr-4 max-w-xs truncate text-gray-700">
                        {log.detail || "—"}
                      </td>

                      <td className="py-3 pr-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${getResultBadge(
                            log.status
                          )}`}
                        >
                          ● {log.status}
                        </span>
                      </td>

                      <td
                        className="py-3 text-right font-mono text-[10px] text-gray-400"
                        title={log.curr_hash}
                      >
                        {log.curr_hash.slice(0, 6)}...{log.curr_hash.slice(-4)}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Footer & Pagination */}
        {data && data.total > 0 && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs text-gray-400 pt-3 border-t border-gray-100 gap-2">
            <span>
              Menampilkan {data.logs.length} dari {data.total} entri · Log disimpan append-only dengan rantai hash SHA-256
            </span>

            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(5, data.total_pages) }, (_, i) => i + 1).map((p) => (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`w-7 h-7 rounded-lg font-medium transition ${
                    page === p
                      ? "bg-purple-600 text-white"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
