import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  Bot,
  ChevronRight,
  FileText,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Plus,
  Send,
  Shield,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { api } from "../api/client";
import { LogoutModal } from "../components/LogoutModal";
import { useAuth } from "../context/AuthContext";

interface Citation {
  index: number;
  document_id: string;
  filename: string;
  section_title?: string;
  page_number?: number;
  classification: "Public" | "HR" | "Finance" | "Confidential";
  relevance_score: number;
}

interface Message {
  id: string;
  session_id: string;
  sender: "user" | "assistant";
  content: string;
  status: "SUCCESS" | "QUERY_DENIED" | "PROMPT_INJECTION" | "ERROR";
  blocked_classification?: string | null;
  citations_json: Citation[];
  latency_ms?: number | null;
  created_at: string;
  feedback?: {
    id: string;
    is_positive: boolean;
    comment?: string;
  } | null;
}

interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export const ChatPage: React.FC = () => {
  const { user, canManageDocs, canViewAudit } = useAuth();

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [showLogoutModal, setShowLogoutModal] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load chat sessions
  const loadSessions = async () => {
    try {
      const data = await api.get<ChatSession[]>("/chat/sessions");
      setSessions(data);
      if (data.length > 0 && !activeSessionId) {
        setActiveSessionId(data[0].id);
      }
    } catch (err) {
      console.error("Gagal memuat sesi:", err);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  // Load messages when active session changes
  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }
    const loadMessages = async () => {
      try {
        const data = await api.get<Message[]>(
          `/chat/sessions/${activeSessionId}/messages`
        );
        setMessages(data);
      } catch (err) {
        console.error("Gagal memuat pesan:", err);
      }
    };
    loadMessages();
  }, [activeSessionId]);

  // Scroll to bottom on new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  const handleCreateNewSession = async () => {
    try {
      const newSession = await api.post<ChatSession>("/chat/sessions", {
        title: "Percakapan baru",
      });
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
      setMessages([]);
    } catch (err) {
      console.error("Gagal membuat sesi baru:", err);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    const query = inputText.trim();
    if (!query || isSending) return;

    let targetSessionId = activeSessionId;

    // Jika belum ada sesi, buat sesi terlebih dahulu
    if (!targetSessionId) {
      try {
        const newSession = await api.post<ChatSession>("/chat/sessions", {
          title: query.slice(0, 40),
        });
        setSessions((prev) => [newSession, ...prev]);
        setActiveSessionId(newSession.id);
        targetSessionId = newSession.id;
      } catch (err) {
        console.error("Gagal membuat sesi:", err);
        return;
      }
    }

    // Tampilkan pesan pengguna secara optimistik
    const optimisticUserMsg: Message = {
      id: "temp-" + Date.now(),
      session_id: targetSessionId,
      sender: "user",
      content: query,
      status: "SUCCESS",
      citations_json: [],
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, optimisticUserMsg]);
    setInputText("");
    setIsSending(true);

    try {
      const assistantMsg = await api.post<Message>(
        `/chat/sessions/${targetSessionId}/query`,
        { content: query }
      );
      setMessages((prev) => [...prev, assistantMsg]);
      loadSessions(); // Perbarui judul sesi jika berubah
    } catch (err: any) {
      const errorMsg: Message = {
        id: "err-" + Date.now(),
        session_id: targetSessionId,
        sender: "assistant",
        content: `Terjadi kesalahan saat memproses pertanyaan: ${err.message}`,
        status: "ERROR",
        citations_json: [],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsSending(false);
    }
  };

  const handleFeedback = async (messageId: string, isPositive: boolean) => {
    try {
      await api.post(`/chat/messages/${messageId}/feedback`, {
        is_positive: isPositive,
      });
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId
            ? { ...m, feedback: { id: "fb-" + Date.now(), is_positive: isPositive } }
            : m
        )
      );
    } catch (err) {
      console.error("Gagal mengirim feedback:", err);
    }
  };

  const getClassificationBadge = (classification: string) => {
    switch (classification) {
      case "Public":
        return "bg-emerald-950/60 text-emerald-400 border-emerald-800/60";
      case "HR":
        return "bg-blue-950/60 text-blue-400 border-blue-800/60";
      case "Finance":
        return "bg-amber-950/60 text-amber-400 border-amber-800/60";
      case "Confidential":
        return "bg-rose-950/60 text-rose-400 border-rose-800/60";
      default:
        return "bg-gray-800 text-gray-400 border-gray-700";
    }
  };

  const currentSession = sessions.find((s) => s.id === activeSessionId);
  const userRole = user?.role || "Karyawan";
  const userInitials = (user?.full_name || user?.username || "U")
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="flex h-screen w-screen bg-[#10100F] text-gray-100 overflow-hidden font-sans">
      {/* ======================================================== */}
      {/* SIDEBAR KIRI (Dark #141413) */}
      {/* ======================================================== */}
      <aside className="w-72 bg-[#141413] border-r border-[#242422] flex flex-col justify-between shrink-0">
        <div>
          {/* Header Brand */}
          <div className="p-4 border-b border-[#242422] flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#C92A2A] text-white flex items-center justify-center font-bold shadow-md shadow-red-950/50">
              <Bot className="w-4 h-4" />
            </div>
            <div>
              <span className="text-sm font-bold text-white block tracking-wide">
                Chatbot Cerdas & Aman
              </span>
              <span className="text-[10px] text-gray-400 block">Enterprise RAG</span>
            </div>
          </div>

          {/* Tombol Percakapan Baru */}
          <div className="p-3">
            <button
              onClick={handleCreateNewSession}
              className="w-full py-2.5 px-4 bg-[#C92A2A] hover:bg-[#A61E1E] text-white text-xs font-semibold rounded-xl flex items-center justify-center gap-2 shadow-sm transition"
            >
              <Plus className="w-4 h-4" />
              <span>Percakapan baru</span>
            </button>
          </div>

          {/* Navigasi Panel Khusus Admin / Auditor */}
          {(canManageDocs || canViewAudit) && (
            <div className="px-3 pb-2 pt-1 border-b border-[#242422]">
              <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider px-2 mb-1.5">
                Portal Manajemen
              </div>
              {canManageDocs && (
                <Link
                  to="/admin"
                  className="flex items-center gap-2.5 px-3 py-1.5 text-xs text-gray-300 hover:text-white hover:bg-[#1E1E1C] rounded-lg transition"
                >
                  <LayoutDashboard className="w-3.5 h-3.5 text-red-400" />
                  <span>Portal Admin</span>
                </Link>
              )}
              {canViewAudit && (
                <Link
                  to="/auditor"
                  className="flex items-center gap-2.5 px-3 py-1.5 text-xs text-gray-300 hover:text-white hover:bg-[#1E1E1C] rounded-lg transition"
                >
                  <Shield className="w-3.5 h-3.5 text-purple-400" />
                  <span>Portal Auditor</span>
                </Link>
              )}
            </div>
          )}

          {/* Daftar Riwayat Percakapan */}
          <div className="px-3 py-2 overflow-y-auto max-h-[calc(100vh-280px)]">
            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider px-2 mb-2">
              Riwayat Percakapan
            </div>

            {sessions.length === 0 ? (
              <div className="px-2 py-4 text-xs text-gray-400 italic">
                Belum ada percakapan.
              </div>
            ) : (
              <div className="space-y-1">
                {sessions.map((sess) => {
                  const isActive = sess.id === activeSessionId;
                  return (
                    <button
                      key={sess.id}
                      onClick={() => setActiveSessionId(sess.id)}
                      className={`w-full text-left px-3 py-2 rounded-xl text-xs flex items-center justify-between transition ${
                        isActive
                          ? "bg-[#252523] text-white font-medium border border-[#353532]"
                          : "text-gray-400 hover:bg-[#1C1C1A] hover:text-gray-200"
                      }`}
                    >
                      <div className="flex items-center gap-2 truncate pr-2">
                        <MessageSquare className="w-3.5 h-3.5 shrink-0 opacity-70" />
                        <span className="truncate">{sess.title}</span>
                      </div>
                      {isActive && <ChevronRight className="w-3 h-3 shrink-0 text-red-400" />}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Profil Pengguna Bawah */}
        <div className="p-3 border-t border-[#242422] bg-[#141413]">
          <div className="flex items-center justify-between p-2 rounded-xl bg-[#1C1C1A] border border-[#262624]">
            <div className="flex items-center gap-2.5 truncate">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-red-600 to-rose-400 text-white font-bold text-xs flex items-center justify-center shrink-0">
                {userInitials}
              </div>
              <div className="truncate">
                <span className="text-xs font-semibold text-white block truncate leading-tight">
                  {user?.full_name || user?.username}
                </span>
                <span className="text-[10px] text-gray-400 block truncate">
                  Peran: {userRole}
                </span>
              </div>
            </div>

            <button
              onClick={() => setShowLogoutModal(true)}
              title="Keluar dari sesi"
              className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-[#282826] rounded-lg transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* ======================================================== */}
      {/* AREA UTAMA CHAT */}
      {/* ======================================================== */}
      <main className="flex-1 flex flex-col h-full bg-[#10100F] overflow-hidden">
        {/* Header Atas */}
        <header className="h-14 border-b border-[#242422] px-6 flex items-center justify-between bg-[#141413]/70 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold text-white truncate max-w-md">
              {currentSession?.title || "Percakapan baru"}
            </h2>
          </div>

          <div className="flex items-center gap-3">
            {/* Badge Akses Peran */}
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#1C1C1A] border border-[#2E2E2B] text-[11px] text-gray-300">
              <Shield className="w-3 h-3 text-emerald-400" />
              <span>
                Akses:{" "}
                <strong className="text-white">
                  {user?.allowed_classifications?.join(" · ") || "Public"}
                </strong>
              </span>
            </div>

            {/* Badge Model LLM */}
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#1C1C1A] border border-[#2E2E2B] text-[11px] text-gray-300">
              <Bot className="w-3 h-3 text-red-400" />
              <span>Llama 3 · Ollama</span>
            </div>
          </div>
        </header>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8 text-gray-400">
              <div className="w-16 h-16 rounded-2xl bg-[#1C1C1A] border border-[#2E2E2C] flex items-center justify-center text-red-500 mb-4 shadow-xl shadow-black/40">
                <Bot className="w-8 h-8" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">
                Ada yang bisa dibantu dari dokumen internal?
              </h3>
              <p className="text-xs text-gray-400 max-w-md leading-relaxed">
                Ketik pertanyaan mengenai kebijakan perusahaan, aturan HR, laporan
                keuangan, atau dokumen SOP. Semua jawaban akan dilengkapi dengan sitasi
                sumber resmi.
              </p>
            </div>
          ) : (
            messages.map((msg) => {
              const isUser = msg.sender === "user";

              if (isUser) {
                return (
                  <div key={msg.id} className="flex justify-end">
                    <div className="max-w-2xl bg-[#C92A2A] text-white px-4 py-3 rounded-2xl rounded-tr-sm shadow-md text-sm leading-relaxed">
                      {msg.content}
                    </div>
                  </div>
                );
              }

              // Kartu Penolakan RBAC (QUERY_DENIED) atau PROMPT_INJECTION
              if (
                msg.status === "QUERY_DENIED" ||
                msg.status === "PROMPT_INJECTION"
              ) {
                return (
                  <div key={msg.id} className="flex justify-start">
                    <div className="max-w-2xl w-full bg-amber-950/20 border border-amber-800/40 rounded-2xl p-4 text-xs leading-relaxed text-amber-200">
                      <div className="flex items-center gap-2 text-amber-400 font-bold mb-2">
                        <AlertTriangle className="w-4 h-4 shrink-0" />
                        <span>
                          {msg.status === "PROMPT_INJECTION"
                            ? "Percobaan Prompt Injection Diblokir"
                            : "Informasi tidak tersedia untuk peran Anda"}
                        </span>
                      </div>

                      <p className="text-amber-100/90 mb-3">{msg.content}</p>

                      <div className="flex items-center gap-2 text-[10px]">
                        {msg.blocked_classification && (
                          <span className="px-2 py-0.5 rounded bg-amber-900/50 border border-amber-700/50 text-amber-300 font-medium">
                            Klasifikasi: {msg.blocked_classification}
                          </span>
                        )}
                        <span className="px-2 py-0.5 rounded bg-amber-950/80 border border-amber-800/50 text-amber-400">
                          Dicatat di log audit
                        </span>
                      </div>
                    </div>
                  </div>
                );
              }

              // Jawaban Asisten Normal dengan Sitasi
              return (
                <div key={msg.id} className="flex justify-start">
                  <div className="max-w-3xl w-full space-y-3">
                    {/* Bubble Teks Jawaban */}
                    <div className="bg-[#1C1C1A] border border-[#2E2E2B] text-gray-200 px-5 py-4 rounded-2xl rounded-tl-sm shadow-sm text-sm leading-relaxed">
                      <div className="whitespace-pre-wrap">{msg.content}</div>
                    </div>

                    {/* Kartu Sumber Dokumen (Jika ada sitasi) */}
                    {msg.citations_json && msg.citations_json.length > 0 && (
                      <div className="p-3 bg-[#161614] border border-[#242422] rounded-xl space-y-2">
                        <div className="text-[11px] font-bold text-gray-400 flex items-center gap-1.5 uppercase tracking-wider">
                          <FileText className="w-3.5 h-3.5 text-red-400" />
                          <span>Sumber Dokumen ({msg.citations_json.length})</span>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                          {msg.citations_json.map((cite) => (
                            <div
                              key={cite.index}
                              className="p-2.5 rounded-lg bg-[#1E1E1C] border border-[#2A2A28] flex flex-col justify-between text-xs"
                            >
                              <div>
                                <div className="flex items-center justify-between gap-1 mb-1">
                                  <span className="font-bold text-white text-xs truncate">
                                    [{cite.index}] {cite.filename}
                                  </span>
                                  <span
                                    className={`px-1.5 py-0.5 text-[9px] font-semibold rounded border ${getClassificationBadge(
                                      cite.classification
                                    )}`}
                                  >
                                    {cite.classification}
                                  </span>
                                </div>

                                <p className="text-[11px] text-gray-400 truncate">
                                  {cite.section_title || "Bagian Utama"}{" "}
                                  {cite.page_number && `· Hal. ${cite.page_number}`}
                                </p>
                              </div>

                              <div className="mt-2 text-[10px] text-emerald-400 font-medium">
                                Relevansi {(cite.relevance_score * 100).toFixed(0)}%
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Baris Evaluasi & Latensi */}
                    <div className="flex items-center justify-between text-xs text-gray-400 px-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px]">Apakah jawaban ini membantu?</span>
                        <button
                          onClick={() => handleFeedback(msg.id, true)}
                          disabled={msg.feedback !== undefined && msg.feedback !== null}
                          className={`p-1 rounded hover:bg-[#252523] transition ${
                            msg.feedback?.is_positive === true
                              ? "text-emerald-400 font-bold"
                              : "text-gray-400 hover:text-gray-200"
                          }`}
                        >
                          <ThumbsUp className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleFeedback(msg.id, false)}
                          disabled={msg.feedback !== undefined && msg.feedback !== null}
                          className={`p-1 rounded hover:bg-[#252523] transition ${
                            msg.feedback?.is_positive === false
                              ? "text-red-400 font-bold"
                              : "text-gray-400 hover:text-gray-200"
                          }`}
                        >
                          <ThumbsDown className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      <div className="flex items-center gap-2 text-[10px] text-gray-400">
                        {msg.latency_ms && (
                          <span>
                            Respons dalam {(msg.latency_ms / 1000).toFixed(1)} dtk
                          </span>
                        )}
                        <span>·</span>
                        <span>RBAC Filtered</span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Box Bawah */}
        <footer className="p-4 border-t border-[#242422] bg-[#141413]">
          <form
            onSubmit={handleSendMessage}
            className="max-w-4xl mx-auto relative flex items-center"
          >
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              disabled={isSending}
              placeholder="Tanyakan sesuatu tentang dokumen internal..."
              className="w-full pl-4 pr-12 py-3 text-sm bg-[#1C1C1A] border border-[#2E2E2C] rounded-2xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500/30 focus:border-red-500 transition disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!inputText.trim() || isSending}
              className="absolute right-2 p-2 rounded-xl bg-[#C92A2A] hover:bg-[#A61E1E] text-white disabled:opacity-30 disabled:hover:bg-[#C92A2A] transition"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>

          <p className="text-center text-[10px] text-gray-400 mt-2">
            Chatbot internal dapat membuat kesalahan. Periksa informasi penting pada
            sumber dokumen rujukan.
          </p>
        </footer>
      </main>

      {/* Logout Modal */}
      <LogoutModal
        isOpen={showLogoutModal}
        onClose={() => setShowLogoutModal(false)}
      />
    </div>
  );
};
