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
from typing import Any, Dict, List, Optional

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
    top_k: int = 4,
    similarity_threshold: float = 0.35,
) -> Dict[str, Any]:
    """
    Pipeline lengkap eksekusi kueri RAG:
    1. Sanitasi & Deteksi Prompt Injection
    2. Embedding & Similarity Search RBAC
    3. Deteksi Lintas-Klasifikasi (QUERY_DENIED)
    4. Generasi Jawaban Bersitasi Ollama
    """
    start_time = time.time()

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
    # Tahap 2: Embedding Kueri & Similarity Search RBAC
    # ========================================================
    try:
        query_vec = await create_embedding(query)
    except Exception as e:
        logger.error(f"Gagal membuat embedding kueri: {e}")
        query_vec = [0.0] * 768

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
    # Tahap 4: Generasi Jawaban Bersitasi via Ollama (Llama 3)
    # ========================================================
    relevant_chunks = [
        row for row in allowed_rows if row["score"] is not None and float(row["score"]) >= similarity_threshold
    ]

    # Format array sitasi
    citations: List[Dict[str, Any]] = []
    context_blocks: List[str] = []

    for idx, row in enumerate(relevant_chunks, start=1):
        score_val = round(float(row["score"]), 2)
        citations.append({
            "index": idx,
            "document_id": str(row["document_id"]),
            "filename": row["filename"],
            "section_title": row["section_title"],
            "page_number": row["page_number"],
            "classification": row["classification"],
            "relevance_score": score_val,
        })
        context_blocks.append(
            f"[{idx}] Sumber: {row['filename']} (Hal. {row['page_number']}, {row['section_title']}):\n{row['content']}"
        )

    # Bila tidak ada konteks relevan
    if not relevant_chunks:
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
            "answer": "Maaf, tidak ditemukan informasi yang relevan pada dokumen yang diizinkan untuk peran Anda.",
            "citations": [],
            "blocked_classification": None,
            "latency_ms": latency_ms,
        }

    context_str = "\n\n".join(context_blocks)

    system_prompt = (
        "Anda adalah asisten AI resmi perusahaan yang cerdas dan aman.\n"
        "Tugas Anda adalah menjawab pertanyaan pengguna secara akurat HANYA berdasarkan konteks dokumen yang diberikan.\n"
        "Aturan wajib:\n"
        "1. Jawab HANYA menggunakan fakta yang tertulis pada konteks dokumen.\n"
        "2. Wajib menyertakan nomor sitasi inline dalam format [1], [2], dst. pada akhir kalimat fakta yang merujuk dokumen terkait.\n"
        "3. Jangan mengarang informasi di luar konteks dokumen.\n"
        "4. Gunakan bahasa Indonesia yang baku, profesional, dan padat."
    )

    user_prompt = f"Konteks Dokumen Internal:\n{context_str}\n\nPertanyaan Pengguna: {query}"

    answer_text = ""
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{settings.ollama_url}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "options": {
                        "temperature": 0.1,
                    },
                },
            )
            if resp.status_code == 200:
                answer_text = resp.json().get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.warning(f"Ollama chat gagal atau tidak tersedia: {e}")

    # Fallback jawaban jika LLM belum siap / mock mode aktif
    if not answer_text:
        # Sintesis jawaban deterministik dari chunk relevan pertama
        top_c = relevant_chunks[0]
        answer_text = f"{top_c['content']} [1]"

    latency_ms = int((time.time() - start_time) * 1000)

    # Catat audit log QUERY berhasil
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
