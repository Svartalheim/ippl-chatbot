import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  Database,
  Download,
  Lock,
  MessageSquare,
  RefreshCw,
  Server,
  ShieldAlert,
  Sparkles,
  ThumbsUp,
  UserCheck,
  Users,
} from "lucide-react";
import { api, BASE_URL } from "../../api/client";

interface DashboardData {
  queries_today: number;
  p95_latency_seconds: number;
  active_users_count: number;
  positive_feedback_ratio: number;
  positive_feedbacks_count: number;
  total_feedbacks_count: number;
  hourly_p95_latency: Array<{
    hour: string;
    latency_seconds: number;
    queries_count: number;
  }>;
  services_status: {
    fastapi: { name: string; status: string; uptime: string; latency_ms: number };
    postgres: { name: string; status: string; documents_count: number; vectors_count: number };
    ollama: { name: string; status: string; model: string };
    keycloak: { name: string; status: string; realm: string };
    worker: { name: string; status: string; queue_count: number };
  };
  documents_by_classification: {
    Public: number;
    HR: number;
    Finance: number;
    Confidential: number;
    total: number;
  };
  security_events_24h: {
    prompt_injection_blocked: number;
    rbac_denied: number;
    keycloak_login_failed: number;
  };
}

export const AdminDashboardPage: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadDashboard = async () => {
    setIsLoading(true);
    try {
      const res = await api.get<DashboardData>("/admin/dashboard/health");
      setData(res);
    } catch (err) {
      console.error("Gagal memuat dasbor kesehatan:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  if (isLoading || !data) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-12 text-gray-500">
        <RefreshCw className="w-8 h-8 animate-spin text-red-600 mb-3" />
        <span className="text-sm font-medium">Memuat dasbor kesehatan sistem...</span>
      </div>
    );
  }

  const maxHourlyLatency = Math.max(
    5.0,
    ...data.hourly_p95_latency.map((h) => h.latency_seconds)
  );

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto w-full">
      {/* Header Halaman */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
            Dasbor Kesehatan Sistem
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Pantau layanan, kinerja kueri, dan umpan balik pengguna secara real-time.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full text-xs font-semibold shadow-sm">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>Semua layanan berjalan</span>
          </div>

          <a
            href={`${BASE_URL}/audit/export-csv`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-xs font-medium rounded-xl shadow-sm transition"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Unduh laporan</span>
          </a>
        </div>
      </div>

      {/* 4 Kartu KPI Utama */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1 */}
        <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-sm">
          <div className="flex items-center justify-between text-gray-500 text-xs mb-2">
            <span className="font-medium">Kueri hari ini</span>
            <MessageSquare className="w-4 h-4 text-red-500" />
          </div>
          <div className="text-2xl font-extrabold text-gray-900">
            {data.queries_today.toLocaleString("id-ID")}
          </div>
          <p className="text-[11px] text-emerald-600 font-medium mt-1">
            +12% dari kemarin
          </p>
        </div>

        {/* KPI 2 */}
        <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-sm">
          <div className="flex items-center justify-between text-gray-500 text-xs mb-2">
            <span className="font-medium">Waktu respons p95</span>
            <Clock className="w-4 h-4 text-blue-500" />
          </div>
          <div className="text-2xl font-extrabold text-gray-900">
            {data.p95_latency_seconds.toFixed(1).replace(".", ",")} dtk
          </div>
          <p className="text-[11px] text-emerald-600 font-medium mt-1 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" />
            <span>Target &lt; 5 dtk tercapai</span>
          </p>
        </div>

        {/* KPI 3 */}
        <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-sm">
          <div className="flex items-center justify-between text-gray-500 text-xs mb-2">
            <span className="font-medium">Pengguna aktif</span>
            <Users className="w-4 h-4 text-purple-500" />
          </div>
          <div className="text-2xl font-extrabold text-gray-900">
            {data.active_users_count}
          </div>
          <p className="text-[11px] text-gray-500 font-medium mt-1">
            Uji kapasitas: 500 pengguna
          </p>
        </div>

        {/* KPI 4 */}
        <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-sm">
          <div className="flex items-center justify-between text-gray-500 text-xs mb-2">
            <span className="font-medium">Umpan balik positif</span>
            <ThumbsUp className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-extrabold text-gray-900">
            {Math.round(data.positive_feedback_ratio)}%
          </div>
          <p className="text-[11px] text-gray-500 font-medium mt-1">
            {data.positive_feedbacks_count} dari {data.total_feedbacks_count} penilaian
          </p>
        </div>
      </div>

      {/* Baris Tengah: Grafik Latensi & Status Layanan */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Grafik Batang Latensi p95 (2/3 lebar) */}
        <div className="lg:col-span-2 bg-white p-6 rounded-2xl border border-gray-200/80 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-gray-900">
                  Latensi kueri p95
                </h3>
                <span className="text-xs text-gray-400">
                  24 jam terakhir · per jam
                </span>
              </div>

              <div className="flex items-center gap-4 text-xs">
                <span className="flex items-center gap-1.5 text-red-600 font-medium">
                  <span className="w-2.5 h-2.5 rounded-full bg-red-500"></span>
                  p95 (dtk)
                </span>
                <span className="flex items-center gap-1.5 text-gray-400 font-medium">
                  <span className="w-4 h-0.5 bg-gray-300"></span>
                  Target 5 dtk
                </span>
              </div>
            </div>

            {/* Visualisasi Bar Chart */}
            <div className="h-44 flex items-end gap-1.5 pt-6 pb-2 border-b border-gray-100">
              {data.hourly_p95_latency.map((slot, i) => {
                const heightPercent = Math.min(
                  100,
                  Math.round((slot.latency_seconds / maxHourlyLatency) * 100)
                );
                return (
                  <div
                    key={i}
                    className="flex-1 flex flex-col items-center justify-end h-full group relative"
                  >
                    {/* Tooltip Hover */}
                    <div className="absolute -top-10 opacity-0 group-hover:opacity-100 bg-gray-900 text-white text-[10px] px-2 py-1 rounded shadow pointer-events-none transition z-10 whitespace-nowrap">
                      {slot.hour}: {slot.latency_seconds}s ({slot.queries_count} kueri)
                    </div>
                    <div
                      style={{ height: `${heightPercent}%` }}
                      className={`w-full rounded-t transition-all ${
                        slot.latency_seconds > 4.5
                          ? "bg-amber-400 group-hover:bg-amber-500"
                          : "bg-red-400/80 group-hover:bg-red-600"
                      }`}
                    ></div>
                  </div>
                );
              })}
            </div>

            {/* Label Waktu Horisontal */}
            <div className="flex justify-between text-[10px] text-gray-400 pt-2 font-mono">
              <span>00:00</span>
              <span>06:00</span>
              <span>12:00</span>
              <span>18:00</span>
              <span>Sekarang</span>
            </div>
          </div>
        </div>

        {/* Status Layanan (1/3 lebar) */}
        <div className="bg-white p-6 rounded-2xl border border-gray-200/80 shadow-sm flex flex-col justify-between">
          <h3 className="text-sm font-bold text-gray-900 mb-4">Status layanan</h3>

          <div className="space-y-4">
            {/* FastAPI */}
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div className="flex items-center gap-2.5">
                <Server className="w-4 h-4 text-gray-400" />
                <div>
                  <span className="text-xs font-bold text-gray-800 block">FastAPI (backend)</span>
                  <span className="text-[11px] text-gray-400">
                    Uptime {data.services_status.fastapi.uptime} · {data.services_status.fastapi.latency_ms} ms
                  </span>
                </div>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-200">
                ● Sehat
              </span>
            </div>

            {/* PostgreSQL */}
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div className="flex items-center gap-2.5">
                <Database className="w-4 h-4 text-gray-400" />
                <div>
                  <span className="text-xs font-bold text-gray-800 block">PostgreSQL + pgvector</span>
                  <span className="text-[11px] text-gray-400">
                    {data.services_status.postgres.documents_count} dokumen · {data.services_status.postgres.vectors_count} vektor
                  </span>
                </div>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-200">
                ● Sehat
              </span>
            </div>

            {/* Ollama */}
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div className="flex items-center gap-2.5">
                <Sparkles className="w-4 h-4 text-gray-400" />
                <div>
                  <span className="text-xs font-bold text-gray-800 block">Ollama · Llama 3 8B</span>
                  <span className="text-[11px] text-gray-400">
                    GPU 88% · 31 token/dtk
                  </span>
                </div>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-200">
                ● Sehat
              </span>
            </div>

            {/* Keycloak */}
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div className="flex items-center gap-2.5">
                <UserCheck className="w-4 h-4 text-gray-400" />
                <div>
                  <span className="text-xs font-bold text-gray-800 block">Keycloak (IdP)</span>
                  <span className="text-[11px] text-gray-400">312 sesi JWT aktif</span>
                </div>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-200">
                ● Sehat
              </span>
            </div>

            {/* Worker Ingestion */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <Activity className="w-4 h-4 text-gray-400" />
                <div>
                  <span className="text-xs font-bold text-gray-800 block">Worker ingestion</span>
                  <span className="text-[11px] text-gray-400">
                    {data.services_status.worker.queue_count} dokumen dalam antrean
                  </span>
                </div>
              </div>
              <span
                className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                  data.services_status.worker.status === "Sibuk"
                    ? "bg-amber-50 text-amber-700 border-amber-200"
                    : "bg-emerald-50 text-emerald-700 border-emerald-200"
                }`}
              >
                ● {data.services_status.worker.status}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Baris Bawah: Dokumen per Klasifikasi & Kejadian Keamanan */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Dokumen per Klasifikasi */}
        <div className="bg-white p-6 rounded-2xl border border-gray-200/80 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-gray-900">Dokumen per klasifikasi</h3>
            <span className="text-xs text-gray-400">
              Total {data.documents_by_classification.total} dokumen
            </span>
          </div>

          <div className="space-y-3.5">
            {[
              {
                label: "Public",
                count: data.documents_by_classification.Public,
                barColor: "bg-emerald-500",
              },
              {
                label: "HR",
                count: data.documents_by_classification.HR,
                barColor: "bg-blue-600",
              },
              {
                label: "Finance",
                count: data.documents_by_classification.Finance,
                barColor: "bg-amber-500",
              },
              {
                label: "Confidential",
                count: data.documents_by_classification.Confidential,
                barColor: "bg-red-600",
              },
            ].map((item) => {
              const maxDocs = Math.max(1, data.documents_by_classification.total);
              const percent = Math.round((item.count / maxDocs) * 100);
              return (
                <div key={item.label} className="space-y-1">
                  <div className="flex justify-between text-xs font-medium">
                    <span className="text-gray-700">{item.label}</span>
                    <span className="text-gray-900 font-bold">{item.count}</span>
                  </div>
                  <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      style={{ width: `${Math.max(4, percent)}%` }}
                      className={`h-full rounded-full ${item.barColor} transition-all duration-500`}
                    ></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Kejadian Keamanan · 24 Jam */}
        <div className="bg-white p-6 rounded-2xl border border-gray-200/80 shadow-sm flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-gray-900 mb-4">
              Kejadian keamanan · 24 jam
            </h3>

            <div className="space-y-4">
              <div className="flex items-center gap-3 p-3 rounded-xl bg-red-50/70 border border-red-100">
                <AlertTriangle className="w-5 h-5 text-red-600 shrink-0" />
                <div>
                  <span className="text-xs font-bold text-gray-900 block">
                    {data.security_events_24h.prompt_injection_blocked} percobaan prompt injection diblokir
                  </span>
                  <span className="text-[11px] text-gray-500">
                    Sistem otomatis menghentikan kueri sebelum LLM
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-3 p-3 rounded-xl bg-amber-50/70 border border-amber-100">
                <Lock className="w-5 h-5 text-amber-600 shrink-0" />
                <div>
                  <span className="text-xs font-bold text-gray-900 block">
                    {data.security_events_24h.rbac_denied} kueri ditolak filter RBAC
                  </span>
                  <span className="text-[11px] text-gray-500">
                    Dokumen terkait di luar klasifikasi izin peran pengguna
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-3 p-3 rounded-xl bg-gray-50 border border-gray-200">
                <ShieldAlert className="w-5 h-5 text-gray-600 shrink-0" />
                <div>
                  <span className="text-xs font-bold text-gray-900 block">
                    {data.security_events_24h.keycloak_login_failed} login gagal di Keycloak
                  </span>
                  <span className="text-[11px] text-gray-500">
                    Upaya login dengan kredensial salah atau token expired
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-gray-100 mt-4">
            <Link
              to="/auditor"
              className="inline-flex items-center gap-1.5 text-xs font-bold text-red-600 hover:text-red-700 transition"
            >
              <span>Lihat detail di log audit</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
