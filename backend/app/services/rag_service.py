"""
Layanan RAG (Retrieval-Augmented Generation) & Filter RBAC
Menangani:
1. Sanitasi input & deteksi prompt injection.
2. Embedding kueri & similarity search dengan filter RBAC (pgvector).
3. Deteksi penolakan akses lintas-klasifikasi (QUERY_DENIED).
4. Generasi respons bersitasi inline [1], [2] via Ollama (Llama 3).
5. Pencatatan audit log otomatis (QUERY, QUERY_DENIED, PROMPT_INJECTION).
"""
import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..services.audit_service import record_audit_log
from ..services.ingestion_service import create_embedding

logger = logging.getLogger(__name__)

# Pola regex deteksi serangan prompt injection
PROMPT_INJECTION_PATTERNS = [
    r"abaikan\s+instruksi\s+sebelumnya",
    r"ignore\s+(?:all\s+)?previous\s+instructions",
    r"system\s*prompt",
    r"bypass\s+rbac",
    r"act\s+as\s+admin",
    r"jailbreak",
    r"developer\s+mode",
    r"tampilkan\s+semua\s+dokumen\s+rahasia",
    r"tampilkan\s+instruksi\s+sistem",
    r"reveal\s+(?:the\s+)?secret",
    r"disregard\s+the\s+above",
    r"override\s+system",
    r"sudo\s+mode",
]
COMPILED_INJECTION_REGEX = [
    re.compile(p, re.IGNORECASE) for p in PROMPT_INJECTION_PATTERNS
]


def check_prompt_injection(query: str) -> bool:
    """
    Memeriksa apakah input kueri mengandung pola prompt injection.
    """
    for pattern in COMPILED_INJECTION_REGEX:
        if pattern.search(query):
            return True
    return False


async def execute_rag_query(
    session: AsyncSession,
    query: str,
    user_name: str,
    user_role: str,
    allowed_classifications: List[str],
    user_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
    top_k: Optional[int] = None,
    similarity_threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Pipeline lengkap eksekusi kueri RAG:
    1. Sanitasi & Deteksi Prompt Injection
    2. Embedding & Similarity Search RBAC
    3. Deteksi Lintas-Klasifikasi (QUERY_DENIED)
    4. Generasi Jawaban Bersitasi Ollama
    """
    start_time = time.time()
    top_k = top_k or settings.rag_top_k
    if similarity_threshold is None:
        similarity_threshold = settings.rag_similarity_threshold

    # ========================================================
    # Tahap 1: Sanitasi Input & Deteksi Prompt Injection
    # ========================================================
    if check_prompt_injection(query):
        latency_ms = int((time.time() - start_time) * 1000)
        logger.warning(
            f"Prompt injection terdeteksi dari pengguna '{user_name}' ({user_role}): {query}"
        )

        await record_audit_log(
            session=session,
            actor_name=user_name,
            actor_role=user_role,
            action="PROMPT_INJECTION",
            detail=f'Pola serangan prompt injection diblokir pada kueri: "{query[:60]}"',
            status="Diblokir",
            actor_user_id=user_id,
            ip_address=ip_address,
        )

        return {
            "status": "PROMPT_INJECTION",
            "answer": (
                "Permintaan Anda diblokir oleh sistem keamanan karena terdeteksi pola manipulasi prompt "
                "atau upaya bypass kontrol akses."
            ),
            "citations": [],
            "blocked_classification": None,
            "latency_ms": latency_ms,
        }

    # ========================================================
    # Tahap 1b: Pertanyaan tentang sistem ("dokumen apa yang bisa saya akses?")
    # dijawab langsung dari database, bukan lewat RAG.
    # ========================================================
    if is_small_talk(query):
        return await _canned_result(
            session, start_time, user_name, user_role, user_id, ip_address, query,
            answer=_small_talk_answer(query, user_name, allowed_classifications),
            detail_suffix="sapaan",
        )

    if is_document_list_question(query):
        return await _document_list_result(
            session, start_time, user_name, user_role, allowed_classifications, user_id, ip_address, query
        )

    # ========================================================
    # Tahap 2: Embedding Kueri & Similarity Search RBAC
    # ========================================================
    try:
        query_vec = await create_embedding(query, kind="query")
    except Exception as e:
        logger.error(f"Gagal membuat embedding kueri: {e}")
        return await _error_result(
            session, start_time, user_name, user_role, user_id, ip_address, query,
            reason=f"embedding gagal: {e}",
        )

    query_vec_str = "[" + ",".join(str(round(x, 6)) for x in query_vec) + "]"

    # 1. Query Top-K DENGAN filter klasifikasi yang diizinkan untuk peran pengguna
    sql_allowed = text(
        """
        SELECT 
            dc.id,
            dc.document_id,
            dc.chunk_index,
            dc.content,
            dc.page_number,
            dc.section_title,
            dc.classification,
            d.filename,
            (1 - (dc.embedding <=> CAST(:query_vec AS vector))) AS score
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE dc.classification = ANY(:allowed_classifications)
        ORDER BY dc.embedding <=> CAST(:query_vec AS vector) ASC
        LIMIT :top_k;
        """
    )

    try:
        res_allowed = await session.execute(
            sql_allowed,
            {
                "query_vec": query_vec_str,
                "allowed_classifications": allowed_classifications,
                "top_k": top_k,
            },
        )
        allowed_rows = res_allowed.mappings().all()
    except Exception as e:
        logger.warning(f"Similarity search allowed gagal / fallback: {e}")
        allowed_rows = []

    # 2. Query pemeriksaan lintas-klasifikasi TANPA filter RBAC (k=1)
    sql_global = text(
        """
        SELECT 
            dc.id,
            dc.document_id,
            dc.chunk_index,
            dc.content,
            dc.page_number,
            dc.section_title,
            dc.classification,
            d.filename,
            (1 - (dc.embedding <=> CAST(:query_vec AS vector))) AS score
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        ORDER BY dc.embedding <=> CAST(:query_vec AS vector) ASC
        LIMIT 1;
        """
    )

    try:
        res_global = await session.execute(sql_global, {"query_vec": query_vec_str})
        global_row = res_global.mappings().first()
    except Exception as e:
        logger.warning(f"Similarity search global gagal / fallback: {e}")
        global_row = None

    # ========================================================
    # Tahap 3: Deteksi Akses RBAC (QUERY_DENIED)
    # ========================================================
    best_allowed_score = (
        float(allowed_rows[0]["score"]) if allowed_rows and allowed_rows[0]["score"] is not None else 0.0
    )
    best_global_score = (
        float(global_row["score"]) if global_row and global_row["score"] is not None else 0.0
    )

    # Deteksi bila pertanyaan relevan dengan dokumen terlarang
    if (
        global_row is not None
        and global_row["classification"] not in allowed_classifications
        and best_global_score >= similarity_threshold
        and best_allowed_score < similarity_threshold
    ):
        blocked_class = global_row["classification"]
        latency_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"QUERY_DENIED untuk pengguna '{user_name}' ({user_role}): dokumen terhalang [{blocked_class}]"
        )

        await record_audit_log(
            session=session,
            actor_name=user_name,
            actor_role=user_role,
            action="QUERY_DENIED",
            detail=f'Kueri diblokir filter RBAC karena terkait dokumen klasifikasi {blocked_class}',
            status="Ditolak RBAC",
            actor_user_id=user_id,
            ip_address=ip_address,
        )

        return {
            "status": "QUERY_DENIED",
            "answer": (
                f"Tidak ada dokumen yang dapat diakses peran {user_role} untuk pertanyaan ini. "
                f"Dokumen terkait diklasifikasikan sebagai {blocked_class}. "
                f"Hubungi Admin jika Anda memerlukan akses."
            ),
            "citations": [],
            "blocked_classification": blocked_class,
            "latency_ms": latency_ms,
        }

    # ========================================================
    # Tahap 4: Pilih konteks yang benar-benar relevan
    # ========================================================
    # Absolut: skor >= ambang. Relatif: tidak jauh di bawah skor terbaik, agar chunk
    # "kebetulan mirip" tidak ikut menjadi sumber.
    relevant_chunks = [
        row for row in allowed_rows
        if row["score"] is not None
        and float(row["score"]) >= similarity_threshold
        and float(row["score"]) >= best_allowed_score - settings.rag_relative_margin
    ]

    if not relevant_chunks:
        logger.warning(
            "RAG tidak ditemukan (retrieval): kueri=%r ambang=%.2f skor_teratas=%s",
            query[:80], similarity_threshold,
            [(r["filename"], round(float(r["score"] or 0), 3)) for r in allowed_rows],
        )
        return await _no_answer_result(
            session, start_time, user_name, user_role, user_id, ip_address, query
        )

    context_blocks: List[str] = []
    for idx, row in enumerate(relevant_chunks, start=1):
        context_blocks.append(
            f"[{idx}] Sumber: {row['filename']} (Hal. {row['page_number']}, {row['section_title']}):\n{row['content']}"
        )
    context_str = "\n\n".join(context_blocks)

    # ========================================================
    # Tahap 5: Generasi Jawaban Bersitasi via Ollama
    # ========================================================
    system_prompt = (
        "Anda adalah asisten AI internal perusahaan yang menjawab berdasarkan dokumen.\n"
        "Aturan:\n"
        "1. Jawab menggunakan informasi dari konteks dokumen di bawah. Jangan menambah fakta yang tidak ada di konteks.\n"
        "2. Jika pengguna menanyakan isi, ringkasan, atau penjelasan sebuah dokumen, rangkum informasi dokumen itu dari konteks.\n"
        "3. Jika konteks hanya menjawab sebagian, jawab bagian yang ada dan sebutkan bagian yang tidak tersedia.\n"
        "4. Hanya jika TIDAK ADA satu pun bagian konteks yang berkaitan dengan pertanyaan, balas persis: "
        f"\"{NOT_FOUND_ANSWER}\"\n"
        "5. Akhiri setiap kalimat fakta dengan nomor sumbernya, misalnya [1] atau [2]. "
        "Kutip hanya nomor sumber yang benar-benar Anda gunakan.\n"
        "6. Jawab dalam bahasa Indonesia yang baku dan ringkas."
    )
    user_prompt = f"Konteks Dokumen Internal:\n{context_str}\n\nPertanyaan Pengguna: {query}"

    try:
        answer_text = await _ollama_chat(system_prompt, user_prompt)
    except Exception as e:
        logger.error(f"Generasi jawaban Ollama gagal: {e}")
        return await _error_result(
            session, start_time, user_name, user_role, user_id, ip_address, query,
            reason=f"LLM gagal: {e}",
        )

    if _is_not_found(answer_text):
        logger.warning(
            "RAG tidak ditemukan (LLM menolak): kueri=%r sumber=%s jawaban_llm=%r",
            query[:80],
            [(r["filename"], round(float(r["score"]), 3)) for r in relevant_chunks],
            answer_text[:200],
        )
        return await _no_answer_result(
            session, start_time, user_name, user_role, user_id, ip_address, query
        )

    # Hanya sumber yang benar-benar dikutip di jawaban yang ditampilkan, lalu nomor
    # sitasi diurutkan ulang (mis. jawaban hanya mengutip [3] -> menjadi [1]).
    answer_text, citations = _renumber_citations(answer_text, relevant_chunks)
    if not citations:
        # LLM menjawab tanpa sitasi: tampilkan sumber terbaik saja agar tetap dapat dilacak.
        top = relevant_chunks[0]
        citations = [_citation(1, top)]

    latency_ms = int((time.time() - start_time) * 1000)
    await record_audit_log(
        session=session,
        actor_name=user_name,
        actor_role=user_role,
        action="QUERY",
        detail=f'"{query[:40]}..." · {len(citations)} sumber',
        status="Berhasil",
        actor_user_id=user_id,
        ip_address=ip_address,
    )

    return {
        "status": "SUCCESS",
        "answer": answer_text,
        "citations": citations,
        "blocked_classification": None,
        "latency_ms": latency_ms,
    }


# ============================================================
# Helper
# ============================================================
NOT_FOUND_ANSWER = "Informasi tersebut tidak ditemukan dalam dokumen yang dapat Anda akses."
_CITATION_RE = re.compile(r"\[(\d+)\]")


def _is_not_found(answer: str) -> bool:
    normalized = answer.strip().strip('"').lower()
    return not normalized or normalized.startswith(NOT_FOUND_ANSWER[:40].lower())


def _citation(index: int, row: Any) -> Dict[str, Any]:
    return {
        "index": index,
        "document_id": str(row["document_id"]),
        "filename": row["filename"],
        "section_title": row["section_title"],
        "page_number": row["page_number"],
        "classification": row["classification"],
        "relevance_score": round(float(row["score"]), 2),
    }


def _renumber_citations(answer: str, rows: List[Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """Pertahankan hanya sitasi yang dikutip & valid, beri nomor ulang 1..n sesuai urutan muncul."""
    mapping: Dict[int, int] = {}
    for m in _CITATION_RE.finditer(answer):
        old = int(m.group(1))
        if 1 <= old <= len(rows) and old not in mapping:
            mapping[old] = len(mapping) + 1

    def repl(m: "re.Match[str]") -> str:
        old = int(m.group(1))
        return f"[{mapping[old]}]" if old in mapping else ""  # buang nomor sitasi fiktif

    new_answer = _CITATION_RE.sub(repl, answer).strip()
    citations = [_citation(new, rows[old - 1]) for old, new in sorted(mapping.items(), key=lambda kv: kv[1])]
    return new_answer, citations


async def _ollama_chat(system_prompt: str, user_prompt: str) -> str:
    async with httpx.AsyncClient(timeout=settings.ollama_chat_timeout) as client:
        resp = await client.post(
            f"{settings.ollama_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "options": {"temperature": 0.1},
            },
        )
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} dari Ollama: {resp.text[:200]}")
    content = resp.json().get("message", {}).get("content", "").strip()
    if not content:
        raise RuntimeError("Ollama mengembalikan jawaban kosong")
    return content


async def _no_answer_result(session, start_time, user_name, user_role, user_id, ip_address, query):
    latency_ms = int((time.time() - start_time) * 1000)
    await record_audit_log(
        session=session,
        actor_name=user_name,
        actor_role=user_role,
        action="QUERY",
        detail=f'"{query[:40]}..." · 0 sumber',
        status="Berhasil",
        actor_user_id=user_id,
        ip_address=ip_address,
    )
    return {
        "status": "SUCCESS",
        "answer": NOT_FOUND_ANSWER,
        "citations": [],
        "blocked_classification": None,
        "latency_ms": latency_ms,
    }


async def _error_result(session, start_time, user_name, user_role, user_id, ip_address, query, reason):
    latency_ms = int((time.time() - start_time) * 1000)
    await record_audit_log(
        session=session,
        actor_name=user_name,
        actor_role=user_role,
        action="QUERY",
        detail=f'"{query[:40]}..." · gagal ({reason[:80]})',
        status="Gagal",
        actor_user_id=user_id,
        ip_address=ip_address,
    )
    return {
        "status": "ERROR",
        "answer": "Maaf, layanan AI sedang tidak tersedia. Silakan coba lagi beberapa saat lagi.",
        "citations": [],
        "blocked_classification": None,
        "latency_ms": latency_ms,
    }


_DOC_LIST_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bdokumen\s+apa\s+(saja\s+)?(yang\s+)?(bisa|dapat|boleh)",
        r"\bdaftar\s+(semua\s+)?dokumen\b",
        r"\b(apa|mana)\s+saja\s+dokumen\b",
        r"\bdokumen\s+(yang\s+)?(bisa|dapat|boleh)\s+(saya|aku|kami|gue|gw)\s+(akses|lihat|baca)",
        r"\b(akses|hak\s+akses)\s+(saya|aku)\s+(ke\s+)?dokumen",
        r"\bwhat\s+documents\s+can\s+i\b",
    ]
]


def is_document_list_question(query: str) -> bool:
    return any(p.search(query) for p in _DOC_LIST_PATTERNS)


async def _document_list_result(
    session, start_time, user_name, user_role, allowed_classifications, user_id, ip_address, query
):
    rows = (
        await session.execute(
            text(
                """
                SELECT filename, classification
                FROM documents
                WHERE classification = ANY(:allowed) AND status = 'Terindeks'
                ORDER BY classification, filename
                """
            ),
            {"allowed": list(allowed_classifications)},
        )
    ).mappings().all()

    if not allowed_classifications:
        answer = f"Peran {user_role} tidak memiliki akses ke dokumen apa pun di chatbot ini."
    elif not rows:
        answer = (
            f"Peran {user_role} dapat mengakses dokumen berklasifikasi "
            f"{', '.join(allowed_classifications)}, tetapi belum ada dokumen terindeks."
        )
    else:
        lines = [f"- {r['filename']} ({r['classification']})" for r in rows]
        answer = (
            f"Sebagai {user_role}, Anda dapat mengakses {len(rows)} dokumen "
            f"(klasifikasi: {', '.join(allowed_classifications)}):\n" + "\n".join(lines)
        )

    latency_ms = int((time.time() - start_time) * 1000)
    await record_audit_log(
        session=session,
        actor_name=user_name,
        actor_role=user_role,
        action="QUERY",
        detail=f'"{query[:40]}..." · daftar {len(rows)} dokumen',
        status="Berhasil",
        actor_user_id=user_id,
        ip_address=ip_address,
    )
    return {
        "status": "SUCCESS",
        "answer": answer,
        "citations": [],
        "blocked_classification": None,
        "latency_ms": latency_ms,
    }


_SMALL_TALK_RE = re.compile(
    r"^\s*(halo+|hal+o|hai+|hi+|hello|hey|hei|pagi|siang|sore|malam|"
    r"selamat\s+(pagi|siang|sore|malam)|assalamu.?alaikum|"
    r"terima\s*kasih|makasih|thanks?(\s+you)?|thx|ok(e|ay)?|sip|mantap)"
    r"(\s+(ya|yah|banyak|kak|bot|semua|min))*\s*[!.?,]*\s*$",
    re.IGNORECASE,
)
_THANKS_RE = re.compile(r"terima\s*kasih|makasih|thank|thx", re.IGNORECASE)


def is_small_talk(query: str) -> bool:
    """Sapaan / ucapan terima kasih singkat yang tidak perlu dicari di dokumen."""
    return len(query) <= 40 and bool(_SMALL_TALK_RE.match(query))


def _small_talk_answer(query: str, user_name: str, allowed_classifications: List[str]) -> str:
    first_name = (user_name or "").split(" ")[0] or "Anda"
    if _THANKS_RE.search(query):
        return f"Sama-sama, {first_name}! Silakan tanyakan lagi bila ada yang perlu dicari di dokumen internal."
    scope = ", ".join(allowed_classifications) if allowed_classifications else "tidak ada"
    return (
        f"Halo, {first_name}! Saya asisten dokumen internal perusahaan. "
        f"Tanyakan apa saja tentang dokumen yang dapat Anda akses (klasifikasi: {scope}), "
        "misalnya \"Berapa hari hak cuti tahunan?\" atau \"Dokumen apa saja yang bisa saya akses?\""
    )


async def _canned_result(session, start_time, user_name, user_role, user_id, ip_address, query, answer, detail_suffix):
    latency_ms = int((time.time() - start_time) * 1000)
    await record_audit_log(
        session=session,
        actor_name=user_name,
        actor_role=user_role,
        action="QUERY",
        detail=f'"{query[:40]}..." · {detail_suffix}',
        status="Berhasil",
        actor_user_id=user_id,
        ip_address=ip_address,
    )
    return {
        "status": "SUCCESS",
        "answer": answer,
        "citations": [],
        "blocked_classification": None,
        "latency_ms": latency_ms,
    }

