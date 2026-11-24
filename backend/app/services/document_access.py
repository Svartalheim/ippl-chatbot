"""
Akses baca isi dokumen sumber dengan penegakan matriks RBAC.

Dipakai oleh:
- /admin/documents/{id}/preview|file  (konsol Admin)
- /chat/documents/{id}/preview|file   (sitasi di chat untuk semua pengguna, FR-RESP-004 / NFR-USA-002)

Hak "kelola dokumen" tidak sama dengan hak membaca isi: setiap peran hanya boleh
membuka dokumen yang klasifikasinya ada di allowed_classifications perannya.
Setiap akses (berhasil atau ditolak) dicatat sebagai DOC_VIEW.
"""
import uuid
from typing import Any, Dict

from fastapi import HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import UserInfo, get_user_allowed_classifications
from ..models import Document, DocumentChunk
from .audit_service import record_audit_log
from .ingestion_service import STORAGE_DIR

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


async def get_viewable_document(
    doc_id: uuid.UUID,
    request: Request,
    session: AsyncSession,
    user: UserInfo,
    default_role: str = "Karyawan",
) -> Document:
    doc = (await session.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dokumen tidak ditemukan.")

    role_name = getattr(user, "role_name", None) or default_role
    allowed = await get_user_allowed_classifications(session, role_name)
    user_id = uuid.UUID(user.db_id) if user.db_id else None
    client_ip = request.client.host if request.client else None

    if doc.classification not in allowed:
        await record_audit_log(
            session=session,
            actor_name=user.full_name or user.username,
            actor_role=role_name,
            action="DOC_VIEW",
            detail=f"Akses isi dokumen '{doc.filename}' ({doc.classification}) ditolak matriks RBAC",
            status="Ditolak RBAC",
            actor_user_id=user_id,
            ip_address=client_ip,
        )
        # Pesan tidak menyebut nama dokumen agar tidak membocorkan metadata
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Dokumen berklasifikasi {doc.classification} berada di luar hak akses baca "
                f"peran {role_name} ({', '.join(allowed) or 'tidak ada'})."
            ),
        )

    await record_audit_log(
        session=session,
        actor_name=user.full_name or user.username,
        actor_role=role_name,
        action="DOC_VIEW",
        detail=f"Membuka dokumen '{doc.filename}' ({doc.classification})",
        status="Berhasil",
        actor_user_id=user_id,
        ip_address=client_ip,
    )
    return doc


async def document_preview(session: AsyncSession, doc: Document) -> Dict[str, Any]:
    chunks = (
        await session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc.id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
    ).scalars().all()
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "file_type": doc.file_type,
        "classification": doc.classification,
        "has_file": (STORAGE_DIR / f"{doc.id}_{doc.filename}").exists(),
        "chunks": [
            {
                "chunk_index": c.chunk_index,
                "page_number": c.page_number,
                "section_title": c.section_title,
                "content": c.content,
            }
            for c in chunks
        ],
    }


def document_file_response(doc: Document, download: bool = False) -> FileResponse:
    path = STORAGE_DIR / f"{doc.id}_{doc.filename}"
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File asli tidak tersimpan (mis. dokumen seed). Gunakan pratinjau teks.",
        )
    return FileResponse(
        path,
        media_type=MEDIA_TYPES.get(doc.file_type, "application/octet-stream"),
        filename=doc.filename,
        content_disposition_type="attachment" if download else "inline",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
