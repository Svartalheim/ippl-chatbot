"""
Router LLM yang terintegrasi dengan RAG Service untuk kompatibilitas ke belakang.
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import UserInfo, current_user, get_user_allowed_classifications
from ..db import get_session
from ..services.rag_service import execute_rag_query

router = APIRouter(prefix="/llm", tags=["LLM"])


class ChatIn(BaseModel):
    prompt: str


@router.post("/chat", summary="Chat dengan LLM & RAG")
async def chat(
    body: ChatIn,
    request: Request,
    user: UserInfo = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Kirim prompt ke pipeline RAG dan dapatkan response dengan filter RBAC & sitasi.
    Mempertahankan format response kompatibel dengan client sebelumnya.
    """
    user_id = user.db_user.id if user.db_user else None
    client_ip = request.client.host if request.client else None
    role_name = getattr(user, "role_name", "Karyawan")
    allowed_classifications = await get_user_allowed_classifications(session, role_name)

    result = await execute_rag_query(
        session=session,
        query=body.prompt,
        user_name=user.full_name or user.username,
        user_role=role_name,
        allowed_classifications=allowed_classifications,
        user_id=user_id,
        ip_address=client_ip,
    )

    return {
        "user": user.username,
        "answer": result["answer"],
        "status": result["status"],
        "citations": result.get("citations", []),
        "latency_ms": result.get("latency_ms"),
    }
