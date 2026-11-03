import React, { useState } from "react";
import { LogOut, ShieldCheck, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";

interface LogoutModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const LogoutModal: React.FC<LogoutModalProps> = ({ isOpen, onClose }) => {
  const { logout } = useAuth();
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleConfirmLogout = async () => {
    setIsSubmitting(true);
    try {
      await logout();
    } finally {
      setIsSubmitting(false);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-md bg-white text-gray-900 rounded-2xl shadow-2xl p-6 border border-gray-200">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-red-50 text-red-600 flex items-center justify-center font-bold">
            <LogOut className="w-5 h-5" />
          </div>
          <h2 className="text-xl font-bold text-gray-900">Keluar dari sesi?</h2>
        </div>

        <p className="text-sm text-gray-600 leading-relaxed mb-4">
          Token sesi Anda akan dicabut di Keycloak dan Anda perlu login kembali untuk
          bertanya. Riwayat percakapan tetap tersimpan sesuai kebijakan retensi.
        </p>

        <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-xl border border-gray-100 text-xs text-gray-500 mb-6">
          <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>Aktivitas logout dicatat di log audit imutabel.</span>
        </div>

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-xl transition"
          >
            Batal
          </button>
          <button
            type="button"
            onClick={handleConfirmLogout}
            disabled={isSubmitting}
            className="flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-[#C92A2A] hover:bg-[#A61E1E] rounded-xl shadow-md transition disabled:opacity-50"
          >
            <LogOut className="w-4 h-4" />
            <span>{isSubmitting ? "Keluar..." : "Ya, keluar"}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
