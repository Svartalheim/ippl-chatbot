import React, { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import {
  ArrowLeft,
  Download,
  FileCheck2,
  LogOut,
  Shield,
} from "lucide-react";
import { LogoutModal } from "../components/LogoutModal";
import { useAuth } from "../context/AuthContext";

export const AuditorLayout: React.FC = () => {
  const { user } = useAuth();
  const [showLogoutModal, setShowLogoutModal] = useState(false);

  const userInitials = (user?.full_name || user?.username || "B")
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="flex h-screen w-screen bg-[#F8F9FA] text-gray-900 overflow-hidden font-sans">
      {/* SIDEBAR AUDITOR (Dark #141413) */}
      <aside className="w-64 bg-[#141413] text-gray-300 border-r border-[#262624] flex flex-col justify-between shrink-0">
        <div>
          {/* Header Brand */}
          <div className="p-4 border-b border-[#262624] flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-purple-600 text-white flex items-center justify-center font-bold shadow-md shadow-purple-950/40">
              <Shield className="w-4 h-4" />
            </div>
            <div>
              <span className="text-sm font-bold text-white block tracking-wide">
                Chatbot Cerdas & Aman
              </span>
              <span className="text-[10px] text-purple-400 font-semibold block uppercase tracking-wider">
                Konsol Auditor
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-1">
            <NavLink
              to="/auditor"
              end
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition ${
                  isActive
                    ? "bg-[#252523] text-white border border-[#353532] shadow-sm"
                    : "text-gray-400 hover:text-white hover:bg-[#1E1E1C]"
                }`
              }
            >
              <FileCheck2 className="w-4 h-4 shrink-0" />
              <span>Log Audit</span>
            </NavLink>

            <a
              href="http://localhost:8000/audit/export-csv"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium text-gray-400 hover:text-white hover:bg-[#1E1E1C] transition"
            >
              <Download className="w-4 h-4 shrink-0" />
              <span>Laporan Ekspor</span>
            </a>

            <div className="pt-2 border-t border-[#262624] my-2">
              <Link
                to="/"
                className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium text-gray-400 hover:text-white hover:bg-[#1E1E1C] transition"
              >
                <ArrowLeft className="w-4 h-4 text-gray-400" />
                <span>Kembali ke Chat</span>
              </Link>
            </div>
          </nav>
        </div>

        {/* Profil Bawah */}
        <div className="p-3 border-t border-[#262624]">
          <div className="flex items-center justify-between p-2 rounded-xl bg-[#1C1C1A] border border-[#262624]">
            <div className="flex items-center gap-2.5 truncate">
              <div className="w-8 h-8 rounded-lg bg-purple-600 text-white font-bold text-xs flex items-center justify-center shrink-0">
                {userInitials}
              </div>
              <div className="truncate">
                <span className="text-xs font-semibold text-white block truncate leading-tight">
                  {user?.full_name || user?.username}
                </span>
                <span className="text-[10px] text-purple-300 block truncate">
                  Peran: {user?.role || "Auditor"}
                </span>
              </div>
            </div>

            <button
              onClick={() => setShowLogoutModal(true)}
              title="Keluar"
              className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-[#282826] rounded-lg transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* KONTEN UTAMA AUDITOR */}
      <main className="flex-1 flex flex-col h-full overflow-y-auto bg-[#F8F9FA]">
        <Outlet />
      </main>

      <LogoutModal
        isOpen={showLogoutModal}
        onClose={() => setShowLogoutModal(false)}
      />
    </div>
  );
};
