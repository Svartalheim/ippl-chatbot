import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BookOpen,
  KeyRound,
  Lock,
  LogIn,
  MessageSquare,
  Shield,
  ShieldCheck,
  User,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setIsLoading(true);

    try {
      await login(username, password);
      navigate("/");
    } catch (err: any) {
      setErrorMsg(err.message || "Gagal masuk. Periksa username dan password.");
    } finally {
      setIsLoading(false);
    }
  };

  const setPresetUser = (userVal: string, passVal: string = "password123") => {
    setUsername(userVal);
    setPassword(passVal);
    setErrorMsg(null);
  };

  return (
    <div className="min-h-screen w-full flex flex-col md:flex-row bg-[#0D0D0C]">
      {/* PANEL KIRI (Branding & Fitur) */}
      <div className="w-full md:w-1/2 bg-[#141413] p-8 md:p-16 flex flex-col justify-between border-b md:border-b-0 md:border-r border-[#2C2C2A]">
        <div>
          {/* Logo Brand */}
          <div className="flex items-center gap-3 mb-12">
            <div className="w-10 h-10 rounded-xl bg-[#C92A2A] text-white flex items-center justify-center shadow-lg shadow-red-950/40">
              <MessageSquare className="w-5 h-5" />
            </div>
            <div>
              <span className="text-base font-bold text-white tracking-wide block">
                Chatbot Cerdas & Aman
              </span>
              <span className="text-xs text-gray-400">Enterprise RAG Assistant</span>
            </div>
          </div>

          {/* Headline */}
          <h1 className="text-3xl md:text-4xl font-extrabold text-white leading-tight mb-4">
            Tanya dokumen internal.
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-red-400 to-rose-200">
              Dapat jawaban bersitasi.
            </span>
          </h1>

          <p className="text-sm text-gray-400 leading-relaxed mb-10 max-w-lg">
            Asisten berbasis RAG yang menjawab dari dokumen perusahaan — hanya dari dokumen
            yang boleh Anda akses sesuai peran.
          </p>

          {/* 3 Poin Fitur Utama */}
          <div className="space-y-5">
            <div className="flex items-start gap-4">
              <div className="w-9 h-9 rounded-lg bg-[#222220] border border-[#2E2E2C] flex items-center justify-center text-red-400 shrink-0">
                <BookOpen className="w-4 h-4" />
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-200">
                  Setiap jawaban disertai sitasi sumber dokumen
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  Rujukan bab, halaman, dan nama file PDF/DOCX yang dapat diverifikasi.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <div className="w-9 h-9 rounded-lg bg-[#222220] border border-[#2E2E2C] flex items-center justify-center text-red-400 shrink-0">
                <Lock className="w-4 h-4" />
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-200">
                  Akses dibatasi per peran (RBAC)
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  Empat tingkat klasifikasi dokumen: Public, HR, Finance, Confidential.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <div className="w-9 h-9 rounded-lg bg-[#222220] border border-[#2E2E2C] flex items-center justify-center text-red-400 shrink-0">
                <Shield className="w-4 h-4" />
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-200">
                  Semua kueri tercatat di log audit yang tidak dapat diubah
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  Integritas append-only dengan rantai hash SHA-256 yang dapat diaudit.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer Kiri */}
        <div className="pt-12 text-xs text-gray-400 border-t border-[#232321] mt-8">
          Program Studi Teknik Informatika · Universitas Telkom · 2026
        </div>
      </div>

      {/* PANEL KANAN (Form Login) */}
      <div className="w-full md:w-1/2 p-6 md:p-16 flex items-center justify-center bg-[#10100F]">
        <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl p-8 text-gray-900 border border-gray-100">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Masuk ke akun Anda</h2>
            <p className="text-xs text-gray-500 mt-1">
              Gunakan akun perusahaan yang dikelola Keycloak.
            </p>
          </div>

          {errorMsg && (
            <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700 flex items-start gap-2">
              <span className="font-bold shrink-0">Gagal:</span>
              <span>{errorMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
                Email atau username
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                  <User className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="nama@perusahaan.co.id"
                  className="w-full pl-9 pr-3 py-2.5 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-red-500/30 focus:border-red-500 transition"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Kata sandi
                </label>
                <a href="#forgot" className="text-xs text-red-600 hover:underline">
                  Lupa kata sandi?
                </a>
              </div>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                  <KeyRound className="w-4 h-4" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-9 pr-3 py-2.5 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-red-500/30 focus:border-red-500 transition"
                />
              </div>
            </div>

            <div className="flex items-center">
              <input
                id="remember_me"
                type="checkbox"
                defaultChecked
                className="w-4 h-4 rounded text-red-600 focus:ring-red-500 border-gray-300"
              />
              <label htmlFor="remember_me" className="ml-2 block text-xs text-gray-600">
                Ingat saya di perangkat ini
              </label>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 px-4 bg-[#C92A2A] hover:bg-[#A61E1E] text-white font-semibold rounded-xl shadow-md transition disabled:opacity-50 flex items-center justify-center gap-2 text-sm"
            >
              <LogIn className="w-4 h-4" />
              <span>{isLoading ? "Memproses..." : "Masuk"}</span>
            </button>
          </form>

          <div className="my-5 flex items-center gap-3">
            <div className="h-px bg-gray-200 flex-1"></div>
            <span className="text-xs text-gray-400 uppercase tracking-wider">atau</span>
            <div className="h-px bg-gray-200 flex-1"></div>
          </div>

          <button
            type="button"
            onClick={() => setPresetUser("rina", "password123")}
            className="w-full py-2.5 px-4 bg-gray-50 hover:bg-gray-100 text-gray-800 font-medium rounded-xl border border-gray-200 transition flex items-center justify-center gap-2 text-xs"
          >
            <ShieldCheck className="w-4 h-4 text-red-600" />
            <span>Masuk dengan SSO Keycloak</span>
          </button>

          {/* Quick preset selector untuk kemudahan pengujian developer */}
          <div className="mt-6 pt-4 border-t border-gray-100">
            <p className="text-[11px] font-semibold text-gray-400 mb-2 uppercase tracking-wider">
              Akun Pengujian Demo (Klik Cepat):
            </p>
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => setPresetUser("rina")}
                className="px-2 py-1 text-[11px] rounded bg-blue-50 text-blue-700 hover:bg-blue-100"
              >
                Rina (HR)
              </button>
              <button
                type="button"
                onClick={() => setPresetUser("dimas")}
                className="px-2 py-1 text-[11px] rounded bg-amber-50 text-amber-700 hover:bg-amber-100"
              >
                Dimas (Finance)
              </button>
              <button
                type="button"
                onClick={() => setPresetUser("admin_sistem")}
                className="px-2 py-1 text-[11px] rounded bg-red-50 text-red-700 hover:bg-red-100"
              >
                Admin Sistem
              </button>
              <button
                type="button"
                onClick={() => setPresetUser("budi")}
                className="px-2 py-1 text-[11px] rounded bg-purple-50 text-purple-700 hover:bg-purple-100"
              >
                Budi (Auditor)
              </button>
              <button
                type="button"
                onClick={() => setPresetUser("andi")}
                className="px-2 py-1 text-[11px] rounded bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
              >
                Andi (Karyawan)
              </button>
              <button
                type="button"
                onClick={() => setPresetUser("sari")}
                className="px-2 py-1 text-[11px] rounded bg-rose-50 text-rose-700 hover:bg-rose-100"
              >
                Sari (Manajemen)
              </button>
            </div>
          </div>

          <div className="mt-5 p-3 rounded-xl bg-gray-50 border border-gray-100 flex items-center gap-2 text-[11px] text-gray-500">
            <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>Sesi diamankan token JWT · Aktivitas login dicatat di log audit</span>
          </div>
        </div>
      </div>
    </div>
  );
};
