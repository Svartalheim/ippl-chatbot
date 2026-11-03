import React, { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Database,
  Edit2,
  Eye,
  FileText,
  Search,
  Trash2,
  Upload,
  UploadCloud,
  X,
} from "lucide-react";
import { api } from "../../api/client";
import { DocumentViewerModal } from "../../components/DocumentViewerModal";

interface DocumentItem {
  id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  classification: "Public" | "HR" | "Finance" | "Confidential";
  status: "Terindeks" | "Memproses" | "Gagal";
  error_message?: string | null;
  chunk_count: number;
  uploaded_by?: string | null;
  uploader_name?: string | null;
  created_at: string;
  updated_at: string;
}

interface DocumentsResponse {
  documents: DocumentItem[];
  total: number;
  page: number;
  total_pages: number;
  summary: {
    Semua: number;
    Public: number;
    HR: number;
    Finance: number;
    Confidential: number;
  };
}

export const AdminDocumentsPage: React.FC = () => {
  const [data, setData] = useState<DocumentsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState("");
  const [selectedClass, setSelectedClass] = useState<string>("Semua");
  const [statusFilter, setStatusFilter] = useState<string>("Semua");
  const [page, setPage] = useState(1);

  // Upload state
  const [uploadClass, setUploadClass] = useState<"Public" | "HR" | "Finance" | "Confidential">("Public");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Reindex state
  const [isReindexing, setIsReindexing] = useState(false);

  // Edit classification modal state
  const [viewingDoc, setViewingDoc] = useState<DocumentItem | null>(null);
  const [editingDoc, setEditingDoc] = useState<DocumentItem | null>(null);
  const [newClass, setNewClass] = useState<"Public" | "HR" | "Finance" | "Confidential">("Public");
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  const loadDocuments = async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.append("search", search);
      if (selectedClass) params.append("classification", selectedClass);
      if (statusFilter) params.append("status", statusFilter);
      params.append("page", page.toString());
      params.append("page_size", "10");

      const res = await api.get<DocumentsResponse>(`/admin/documents?${params.toString()}`);
      setData(res);
    } catch (err) {
      console.error("Gagal memuat dokumen:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, [search, selectedClass, statusFilter, page]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadError(null);
    setUploadSuccess(null);
    setIsUploading(true);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("classification", uploadClass);

    try {
      await api.post("/admin/documents/upload", formData);
      setUploadSuccess(`Dokumen "${file.name}" berhasil diunggah dan diindeks.`);
      if (fileInputRef.current) fileInputRef.current.value = "";
      loadDocuments();
    } catch (err: any) {
      setUploadError(err.message || "Gagal mengunggah dokumen.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleReindexAll = async () => {
    if (!confirm("Apakah Anda yakin ingin mengindeks ulang seluruh dokumen?")) return;
    setIsReindexing(true);
    try {
      await api.post("/admin/documents/reindex-all");
      alert("Proses indeks ulang selesai!");
      loadDocuments();
    } catch (err: any) {
      alert("Gagal melakukan reindex: " + err.message);
    } finally {
      setIsReindexing(false);
    }
  };

  const closeViewer = React.useCallback(() => setViewingDoc(null), []);

  const handleDelete = async (doc: DocumentItem) => {
    if (!confirm(`Hapus dokumen "${doc.filename}"? Seluruh chunk vektor juga akan dihapus.`)) return;
    try {
      await api.delete(`/admin/documents/${doc.id}`);
      loadDocuments();
    } catch (err: any) {
      alert("Gagal menghapus dokumen: " + err.message);
    }
  };

  const handleSaveClassification = async () => {
    if (!editingDoc) return;
    setIsSavingEdit(true);
    try {
      await api.patch(`/admin/documents/${editingDoc.id}`, {
        classification: newClass,
      });
      setEditingDoc(null);
      loadDocuments();
    } catch (err: any) {
      alert("Gagal mengubah klasifikasi: " + err.message);
    } finally {
      setIsSavingEdit(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    return (bytes / 1024).toFixed(0) + " KB";
  };

  const getClassificationBadge = (cls: string) => {
    switch (cls) {
      case "Public":
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
      case "HR":
        return "bg-blue-50 text-blue-700 border-blue-200";
      case "Finance":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "Confidential":
        return "bg-red-50 text-red-700 border-red-200";
      default:
        return "bg-gray-100 text-gray-700 border-gray-200";
    }
  };

  const getStatusBadge = (st: string) => {
    switch (st) {
      case "Terindeks":
        return "text-emerald-700 bg-emerald-50 border-emerald-200";
      case "Memproses":
        return "text-blue-700 bg-blue-50 border-blue-200 animate-pulse";
      case "Gagal":
        return "text-red-700 bg-red-50 border-red-200";
      default:
        return "text-gray-700 bg-gray-50 border-gray-200";
    }
  };

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto w-full">
      {/* Header Halaman */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Kelola Dokumen</h1>
          <p className="text-xs text-gray-500 mt-1">
            Unggah dokumen, tetapkan klasifikasi akses, dan pantau status indeks embedding.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleReindexAll}
            disabled={isReindexing}
            className="flex items-center gap-1.5 px-3 py-2 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-xs font-semibold rounded-xl shadow-sm transition disabled:opacity-50"
          >
            <Database className="w-3.5 h-3.5 text-gray-500" />
            <span>{isReindexing ? "Mengindeks..." : "Indeks ulang semua"}</span>
          </button>

          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-1.5 px-4 py-2 bg-[#C92A2A] hover:bg-[#A61E1E] text-white text-xs font-semibold rounded-xl shadow-sm transition"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Unggah dokumen</span>
          </button>
        </div>
      </div>

      {/* Area Dropzone Unggah File */}
      <div className="bg-white p-6 rounded-2xl border-2 border-dashed border-gray-200 text-center relative hover:border-red-300 transition">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc"
          onChange={handleFileUpload}
          disabled={isUploading}
          className="hidden"
        />

        <div className="flex flex-col items-center justify-center max-w-md mx-auto">
          <div className="w-12 h-12 rounded-2xl bg-red-50 text-red-600 flex items-center justify-center mb-3">
            <UploadCloud className="w-6 h-6" />
          </div>

          <h3 className="text-sm font-bold text-gray-900 mb-1">
            {isUploading ? "Sedang memproses & embedding dokumen..." : "Seret file PDF atau DOCX ke sini, atau pilih file"}
          </h3>
          <p className="text-[11px] text-gray-400 mb-4">
            Maks. 20 MB per file · Dokumen di-chunk, diberi metadata klasifikasi, lalu di-embed ke pgvector.
          </p>

          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium">Klasifikasi default:</span>
            <select
              value={uploadClass}
              onChange={(e) => setUploadClass(e.target.value as any)}
              className="text-xs bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1 text-gray-800 font-semibold focus:outline-none focus:ring-1 focus:ring-red-500"
            >
              <option value="Public">Public</option>
              <option value="HR">HR</option>
              <option value="Finance">Finance</option>
              <option value="Confidential">Confidential</option>
            </select>

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="ml-2 px-3 py-1 bg-gray-900 text-white rounded-lg text-xs font-semibold hover:bg-gray-800 transition"
            >
              Pilih File
            </button>
          </div>
        </div>

        {uploadSuccess && (
          <div className="mt-4 p-2.5 rounded-xl bg-emerald-50 text-emerald-700 text-xs flex items-center justify-center gap-1.5 border border-emerald-200">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{uploadSuccess}</span>
          </div>
        )}
        {uploadError && (
          <div className="mt-4 p-2.5 rounded-xl bg-red-50 text-red-700 text-xs flex items-center justify-center gap-1.5 border border-red-200">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{uploadError}</span>
          </div>
        )}
      </div>

      {/* Baris Filter & Search */}
      <div className="bg-white p-4 rounded-2xl border border-gray-200/80 shadow-sm space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
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
              placeholder="Cari nama dokumen..."
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded-xl text-gray-800 focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500"
            />
          </div>

          {/* Classification Filter Pills */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {["Semua", "Public", "HR", "Finance", "Confidential"].map((cls) => {
              const count = data?.summary?.[cls as keyof typeof data.summary] ?? 0;
              const isSelected = selectedClass === cls;
              return (
                <button
                  key={cls}
                  onClick={() => {
                    setSelectedClass(cls);
                    setPage(1);
                  }}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${
                    isSelected
                      ? "bg-gray-900 text-white font-bold"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  <span>{cls}</span>
                  <span className="text-[10px] opacity-75 font-mono">{count}</span>
                </button>
              );
            })}
          </div>

          {/* Status Dropdown Filter */}
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-xs text-gray-400">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="text-xs bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1 text-gray-700 font-medium focus:outline-none"
            >
              <option value="Semua">Semua</option>
              <option value="Terindeks">Terindeks</option>
              <option value="Memproses">Memproses</option>
              <option value="Gagal">Gagal</option>
            </select>
          </div>
        </div>

        {/* Tabel Dokumen */}
        <div className="overflow-x-auto border-t border-gray-100 pt-3">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-gray-400 border-b border-gray-100 font-semibold uppercase text-[10px] tracking-wider">
                <th className="pb-2">Nama Dokumen</th>
                <th className="pb-2">Klasifikasi</th>
                <th className="pb-2">Status Indeks</th>
                <th className="pb-2">Chunk</th>
                <th className="pb-2">Diunggah Oleh</th>
                <th className="pb-2">Diperbarui</th>
                <th className="pb-2 text-right">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-gray-400">
                    Memuat daftar dokumen...
                  </td>
                </tr>
              ) : !data || data.documents.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-gray-400">
                    Tidak ada dokumen yang sesuai dengan kriteria filter.
                  </td>
                </tr>
              ) : (
                data.documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-gray-50/70 transition">
                    <td className="py-3 pr-3">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded bg-red-50 text-red-600 flex items-center justify-center shrink-0">
                          <FileText className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <span className="font-bold text-gray-900 block truncate max-w-xs">
                            {doc.filename}
                          </span>
                          <span className="text-[10px] text-gray-400 uppercase">
                            {doc.file_type} · {formatFileSize(doc.file_size_bytes)}
                          </span>
                        </div>
                      </div>
                    </td>

                    <td className="py-3 pr-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${getClassificationBadge(
                          doc.classification
                        )}`}
                      >
                        ● {doc.classification}
                      </span>
                    </td>

                    <td className="py-3 pr-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${getStatusBadge(
                          doc.status
                        )}`}
                      >
                        ● {doc.status}
                      </span>
                    </td>

                    <td className="py-3 pr-3 font-semibold text-gray-700">
                      {doc.chunk_count > 0 ? doc.chunk_count : "—"}
                    </td>

                    <td className="py-3 pr-3 text-gray-600">
                      {doc.uploader_name || "Admin Sistem"}
                    </td>

                    <td className="py-3 pr-3 text-gray-400 text-[11px]">
                      {new Date(doc.updated_at).toLocaleDateString("id-ID", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </td>

                    <td className="py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => setViewingDoc(doc)}
                          title="Lihat Dokumen"
                          className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => {
                            setEditingDoc(doc);
                            setNewClass(doc.classification);
                          }}
                          title="Ubah Klasifikasi"
                          className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(doc)}
                          title="Hapus Dokumen"
                          className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Baris Pagination */}
        {data && data.total > 0 && (
          <div className="flex items-center justify-between text-xs text-gray-500 pt-3 border-t border-gray-100">
            <span>
              Menampilkan {data.documents.length} dari {data.total} dokumen
            </span>

            <div className="flex items-center gap-1">
              {Array.from({ length: data.total_pages }, (_, i) => i + 1).map((p) => (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`w-7 h-7 rounded-lg font-medium transition ${
                    page === p
                      ? "bg-red-600 text-white"
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

      {/* Modal Penampil Dokumen */}
      {viewingDoc && (
        <DocumentViewerModal
          doc={viewingDoc}
          badgeClass={getClassificationBadge(viewingDoc.classification)}
          onClose={closeViewer}
        />
      )}

      {/* Modal Ubah Klasifikasi Dokumen */}
      {editingDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-sm bg-white rounded-2xl shadow-xl p-5 border border-gray-200 text-gray-900">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-bold text-sm">Ubah Klasifikasi Dokumen</h3>
              <button
                onClick={() => setEditingDoc(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-gray-500 mb-4 truncate font-medium">
              {editingDoc.filename}
            </p>

            <div className="space-y-2 mb-5">
              {(["Public", "HR", "Finance", "Confidential"] as const).map((c) => (
                <label
                  key={c}
                  className={`flex items-center justify-between p-2.5 rounded-xl border cursor-pointer text-xs transition ${
                    newClass === c
                      ? "border-red-500 bg-red-50/40 text-red-950 font-bold"
                      : "border-gray-200 hover:bg-gray-50 text-gray-700"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[9px] font-bold border ${getClassificationBadge(
                        c
                      )}`}
                    >
                      ● {c}
                    </span>
                  </div>
                  <input
                    type="radio"
                    name="classification"
                    value={c}
                    checked={newClass === c}
                    onChange={() => setNewClass(c)}
                    className="text-red-600 focus:ring-red-500"
                  />
                </label>
              ))}
            </div>

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditingDoc(null)}
                className="px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100 rounded-lg transition"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={handleSaveClassification}
                disabled={isSavingEdit}
                className="px-4 py-1.5 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 rounded-lg transition disabled:opacity-50"
              >
                {isSavingEdit ? "Menyimpan..." : "Simpan Perubahan"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
