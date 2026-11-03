import React, { useEffect, useState } from "react";
import { Download, FileText, Loader2, Lock, X } from "lucide-react";
import { api, apiFetchBlob } from "../api/client";

interface PreviewChunk {
  chunk_index: number;
  page_number: number | null;
  section_title: string | null;
  content: string;
}

interface PreviewResponse {
  id: string;
  filename: string;
  file_type: string;
  classification: string;
  has_file: boolean;
  chunks: PreviewChunk[];
}

interface Props {
  doc: { id: string; filename: string; classification: string };
  badgeClass: string;
  onClose: () => void;
}

/**
 * Penampil dokumen untuk halaman Admin:
 * - PDF dengan file asli tersimpan -> dirender di <iframe> (viewer PDF bawaan browser)
 * - DOCX / dokumen seed tanpa file -> teks hasil ekstraksi per chunk
 * Hak baca mengikuti matriks RBAC; backend mengembalikan 403 bila di luar hak akses.
 */
export const DocumentViewerModal: React.FC<Props> = ({ doc, badgeClass, onClose }) => {
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [tab, setTab] = useState<"file" | "text">("file");
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    (async () => {
      try {
        const data = await api.get<PreviewResponse>(`/admin/documents/${doc.id}/preview`);
        if (cancelled) return;
        setPreview(data);

        if (data.has_file && data.file_type === "pdf") {
          const blob = await apiFetchBlob(`/admin/documents/${doc.id}/file`);
          if (cancelled) return;
          objectUrl = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
          setPdfUrl(objectUrl);
          setTab("file");
        } else {
          setTab("text");
        }
      } catch (e: any) {
        if (cancelled) return;
        const msg = e?.message || "Gagal memuat dokumen";
        setIsForbidden(/hak akses|klasifikasi/i.test(msg));
        setError(msg);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      cancelled = true;
      window.removeEventListener("keydown", onKey);
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [doc.id, onClose]);

  const handleDownload = async () => {
    try {
      const blob = await apiFetchBlob(`/admin/documents/${doc.id}/file?download=true`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = doc.filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e?.message || "Gagal mengunduh file");
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-5xl h-[85vh] bg-white rounded-2xl shadow-xl border border-gray-200 text-gray-900 flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between gap-3 px-5 py-3 border-b border-gray-100">
          <div className="flex items-center gap-2 min-w-0">
            <FileText className="w-4 h-4 text-gray-400 shrink-0" />
            <h3 className="font-bold text-sm truncate">{doc.filename}</h3>
            <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold border shrink-0 ${badgeClass}`}>
              ● {doc.classification}
            </span>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {preview?.has_file && (
              <button
                onClick={handleDownload}
                className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-gray-600 hover:bg-gray-100 rounded-lg transition"
              >
                <Download className="w-3.5 h-3.5" /> Unduh
              </button>
            )}
            <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg" title="Tutup (Esc)">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Tabs (hanya bila PDF asli tersedia) */}
        {pdfUrl && (
          <div className="flex gap-1 px-5 pt-2 border-b border-gray-100 text-xs">
            {(["file", "text"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-3 py-1.5 -mb-px border-b-2 transition ${
                  tab === t ? "border-red-600 text-red-700 font-semibold" : "border-transparent text-gray-500 hover:text-gray-800"
                }`}
              >
                {t === "file" ? "Dokumen asli" : `Teks terindeks (${preview?.chunks.length ?? 0} chunk)`}
              </button>
            ))}
          </div>
        )}

        {/* Body */}
        <div className="flex-1 min-h-0 bg-gray-50">
          {isLoading ? (
            <div className="h-full flex items-center justify-center text-gray-400 text-xs gap-2">
              <Loader2 className="w-4 h-4 animate-spin" /> Memuat dokumen...
            </div>
          ) : error ? (
            <div className="h-full flex flex-col items-center justify-center text-center px-8 gap-2">
              {isForbidden && <Lock className="w-6 h-6 text-amber-500" />}
              <p className="text-sm font-semibold text-gray-800">
                {isForbidden ? "Di luar hak akses baca peran Anda" : "Dokumen tidak dapat dimuat"}
              </p>
              <p className="text-xs text-gray-500 max-w-md">{error}</p>
              {isForbidden && <p className="text-[10px] text-gray-400">Percobaan akses ini dicatat di log audit.</p>}
            </div>
          ) : tab === "file" && pdfUrl ? (
            <iframe src={pdfUrl} title={doc.filename} className="w-full h-full border-0" />
          ) : (
            <div className="h-full overflow-y-auto px-6 py-5 space-y-4">
              {!preview?.has_file && (
                <p className="text-[11px] text-gray-500 bg-white border border-gray-200 rounded-lg px-3 py-2">
                  File asli tidak tersimpan untuk dokumen ini (mis. dokumen contoh/seed). Yang ditampilkan adalah teks
                  yang terindeks untuk RAG.
                </p>
              )}
              {preview?.has_file && preview.file_type !== "pdf" && (
                <p className="text-[11px] text-gray-500 bg-white border border-gray-200 rounded-lg px-3 py-2">
                  Browser tidak dapat menampilkan file .{preview.file_type} secara langsung. Gunakan tombol Unduh untuk
                  membuka file asli; di bawah ini teks yang terindeks.
                </p>
              )}
              {preview?.chunks.length === 0 && <p className="text-xs text-gray-400">Belum ada teks terindeks.</p>}
              {preview?.chunks.map((c) => (
                <div key={c.chunk_index} className="bg-white border border-gray-200 rounded-xl p-4">
                  <div className="flex items-center gap-2 text-[10px] text-gray-400 mb-1.5 font-medium">
                    <span>Chunk #{c.chunk_index + 1}</span>
                    {c.page_number != null && <span>· Hal. {c.page_number}</span>}
                    {c.section_title && <span className="truncate">· {c.section_title}</span>}
                  </div>
                  <p className="text-xs text-gray-800 leading-relaxed whitespace-pre-wrap">{c.content}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
