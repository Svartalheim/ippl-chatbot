"""
Router untuk Chat RAG, Sesi Percakapan, Riwayat Pesan, dan Evaluasi Umpan Balik (Feedback).
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import UserInfo, current_user, get_user_allowed_classifications
from ..db import get_session
from ..models import ChatMessage, ChatSession, Feedback
from ..schemas import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    FeedbackBase,
    FeedbackCreate,
    FeedbackResponse,
)
from ..services.audit_service import record_audit_log
from ..services.rag_service import execute_rag_query

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.get("/sessions", response_model=List[ChatSessionResponse], summary="Daftar sesi percakapan")
async def list_sessions(
    session: AsyncSession = Depends(get_session),
    user: UserInfo = Depends(current_user),
):
    """
    Mengambil seluruh riwayat sesi percakapan milik pengguna yang sedang login,
    diurutkan berdasarkan waktu pembaruan terbaru.
    """
    user_id = uuid.UUID(user.db_id) if user.db_id else None
    if not user_id:
        return []

    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
    )
    res = await session.execute(stmt)
    return res.scalars().all()


@router.post("/sessions", response_model=ChatSessionResponse, summary="Buat sesi percakapan baru")
async def create_session(
    body: ChatSessionCreate,
    session: AsyncSession = Depends(get_session),
    user: UserInfo = Depends(current_user),
):
    """
    Membuat sesi chat percakapan baru.
    """
    user_id = uuid.UUID(user.db_id) if user.db_id else None
    new_session = ChatSession(
        id=uuid.uuid4(),
        user_id=user_id,
        title=body.title,
    )
    session.add(new_session)
    await session.commit()
    await session.refresh(new_session)
    return new_session


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse], summary="Ambil riwayat pesan")
async def get_session_messages(
    session_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: UserInfo = Depends(current_user),
):
    """
    Mengambil seluruh riwayat pesan pada sesi percakapan beserta sitasi dan status umpan balik.
    """
    user_id = uuid.UUID(user.db_id) if user.db_id else None

    # Verifikasi kepemilikan sesi
    sess_stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id,
    )
    res_sess = await session.execute(sess_stmt)
    chat_sess = res_sess.scalar_one_or_none()
    if not chat_sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesi percakapan tidak ditemukan.",
        )

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .options(selectinload(ChatMessage.feedback))
        .order_by(ChatMessage.created_at.asc())
    )
    res = await session.execute(stmt)
    return res.scalars().all()


@router.post("/sessions/{session_id}/query", response_model=ChatMessageResponse, summary="Kirim pertanyaan RAG")
async def send_chat_query(
    session_id: uuid.UUID,
    body: ChatMessageCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: UserInfo = Depends(current_user),
):
    """
    Mengirim pertanyaan pengguna ke pipeline RAG:
    - Melakukan sanitasi prompt injection
    - Melakukan similarity search di pgvector dengan filter RBAC
    - Melakukan pemeriksaan lintas-klasifikasi (QUERY_DENIED)
    - Menghasilkan respons bersitasi [1], [2] via LLM Ollama
    - Mencatat user message dan assistant message ke basis data
    """
    user_id = uuid.UUID(user.db_id) if user.db_id else None
    client_ip = request.client.host if request.client else None

    # 1. Verifikasi sesi chat
    sess_stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id,
    )
    res_sess = await session.execute(sess_stmt)
    chat_sess = res_sess.scalar_one_or_none()
    if not chat_sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesi percakapan tidak ditemukan.",
        )

    # 2. Simpan pesan pengguna
    user_msg = ChatMessage(
        id=uuid.uuid4(),
        session_id=session_id,
        sender="user",
        content=body.content,
        status="SUCCESS",
        citations_json=[],
    )
    session.add(user_msg)
    await session.flush()

    # 3. Ambil allowed_classifications untuk peran user
    role_name = getattr(user, "role_name", "Karyawan")
    allowed_classifications = await get_user_allowed_classifications(session, role_name)

    # 4. Eksekusi pipeline RAG
    rag_result = await execute_rag_query(
        session=session,
        query=body.content,
        user_name=user.full_name or user.username,
        user_role=role_name,
        allowed_classifications=allowed_classifications,
        user_id=user_id,
        ip_address=client_ip,
    )

    # 5. Simpan respons asisten
    assistant_msg = ChatMessage(
        id=uuid.uuid4(),
        session_id=session_id,
        sender="assistant",
        content=rag_result["answer"],
        status=rag_result["status"],
        blocked_classification=rag_result.get("blocked_classification"),
        citations_json=rag_result.get("citations", []),
        latency_ms=rag_result.get("latency_ms"),
    )
    session.add(assistant_msg)

    # 6. Perbarui sesi (judul otomatis jika masih judul bawaan & timestamp update)
    if chat_sess.title in ("Percakapan Baru", "Percakapan baru"):
        chat_sess.title = body.content[:45].strip() + ("..." if len(body.content) > 45 else "")
    chat_sess.updated_at = func.now()

    await session.commit()
    await session.refresh(assistant_msg)

    return assistant_msg


@router.post("/messages/{message_id}/feedback", response_model=FeedbackResponse, summary="Kirim evaluasi feedback")
async def submit_feedback(
    message_id: uuid.UUID,
    body: FeedbackBase,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: UserInfo = Depends(current_user),
):
    """
    Menyimpan evaluasi thumbs up / thumbs down dari pengguna untuk pesan asisten,
    dan mencatat event FEEDBACK ke log audit.
    """
    user_id = uuid.UUID(user.db_id) if user.db_id else None
    client_ip = request.client.host if request.client else None

    # Cek pesan
    msg_stmt = select(ChatMessage).where(ChatMessage.id == message_id)
    res_msg = await session.execute(msg_stmt)
    msg = res_msg.scalar_one_or_none()
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pesan tidak ditemukan.",
        )

    # Cek apakah feedback sudah ada sebelumnya
    fb_stmt = select(Feedback).where(Feedback.message_id == message_id)
    res_fb = await session.execute(fb_stmt)
    fb = res_fb.scalar_one_or_none()

    if fb is None:
        fb = Feedback(
            id=uuid.uuid4(),
            message_id=message_id,
            user_id=user_id,
            is_positive=body.is_positive,
            comment=body.comment,
        )
        session.add(fb)
    else:
        fb.is_positive = body.is_positive
        fb.comment = body.comment

    await session.commit()
    await session.refresh(fb)

    # Catat audit log FEEDBACK
    sentiment = "positif (👍)" if body.is_positive else "negatif (👎)"
    role_name = getattr(user, "role_name", "Karyawan")
    await record_audit_log(
        session=session,
        actor_name=user.full_name or user.username,
        actor_role=role_name,
        action="FEEDBACK",
        detail=f"Umpan balik {sentiment} dicatat pada pesan {message_id}",
        status="Berhasil",
        actor_user_id=user_id,
        ip_address=client_ip,
    )

    return fb
