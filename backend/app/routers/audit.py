"""
Router Log Audit untuk Peninjauan Hanya-Baca, Verifikasi Rantai Hash, dan Ekspor CSV.
Dilindungi oleh autentikasi dengan peran Auditor atau Admin (Gambar 7).
"""
import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_roles
from ..db import get_session
from ..models import AuditLog
from ..schemas import AuditLogListResponse, AuditLogResponse, AuditVerificationResponse
from ..services.audit_service import verify_audit_chain

router = APIRouter(
    prefix="/audit",
    tags=["Audit"],
    dependencies=[Depends(require_roles("Auditor", "Admin"))],
)


def _build_audit_query(
    search: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    role: Optional[str] = "Semua",
    action: Optional[str] = "Semua",
    status_filter: Optional[str] = "Semua",
):
    """Membangun query SQLAlchemy dengan filter kriteria audit log"""
    stmt = select(AuditLog).order_by(AuditLog.id.desc())

    if search:
        search_filter = f"%{search}%"
        stmt = stmt.where(
            (AuditLog.actor_name.ilike(search_filter))
            | (AuditLog.detail.ilike(search_filter))
            | (AuditLog.action.ilike(search_filter))
            | (AuditLog.ip_address.ilike(search_filter))
        )

    if start_date:
        stmt = stmt.where(AuditLog.created_at >= start_date)

    if end_date:
        stmt = stmt.where(AuditLog.created_at <= end_date)

    if role and role != "Semua":
        stmt = stmt.where(AuditLog.actor_role == role)

    if action and action != "Semua":
        stmt = stmt.where(AuditLog.action == action)

    if status_filter and status_filter != "Semua":
        stmt = stmt.where(AuditLog.status == status_filter)

    return stmt


@router.get("/logs", response_model=AuditLogListResponse, summary="Daftar entri log audit (Hanya-Baca)")
async def list_audit_logs(
    search: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    role: Optional[str] = "Semua",
    action: Optional[str] = "Semua",
    status_filter: Optional[str] = Query("Semua", alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """
    Mengambil daftar entri audit log (append-only) dengan filter pencarian,
    rentang waktu, peran aktor, jenis aksi, dan status eksekusi.
    """
    stmt = _build_audit_query(
        search=search,
        start_date=start_date,
        end_date=end_date,
        role=role,
        action=action,
        status_filter=status_filter,
    )

    # Hitung total hasil terfilter
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = (await session.execute(count_stmt)).scalar_one() or 0

    # Paginate
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    logs = (await session.execute(stmt)).scalars().all()

    total_pages = max(1, (total_count + page_size - 1) // page_size)

    return AuditLogListResponse(
        logs=[AuditLogResponse.model_validate(log) for log in logs],
        total=total_count,
        page=page,
        total_pages=total_pages,
    )


@router.get("/verify", response_model=AuditVerificationResponse, summary="Verifikasi keutuhan rantai hash audit")
async def verify_chain(session: AsyncSession = Depends(get_session)):
    """
    Memverifikasi integritas kriptografis rantai hash SHA-256 seluruh entri tabel audit_logs.
    Mendeteksi jika ada baris yang disisipkan, dihapus, atau diubah secara manual di database.
    """
    result = await verify_audit_chain(session)
    return AuditVerificationResponse(
        verified=result["verified"],
        total_entries=result["total_entries"],
        checked_at=result["checked_at"],
        broken_at_id=result.get("broken_at_id"),
    )


@router.get("/export-csv", summary="Ekspor log audit ke CSV")
async def export_audit_csv(
    search: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    role: Optional[str] = "Semua",
    action: Optional[str] = "Semua",
    status_filter: Optional[str] = Query("Semua", alias="status"),
    session: AsyncSession = Depends(get_session),
):
    """
    Mengekspor seluruh entri audit log yang sesuai filter ke format text/csv (StreamingResponse).
    """
    stmt = _build_audit_query(
        search=search,
        start_date=start_date,
        end_date=end_date,
        role=role,
        action=action,
        status_filter=status_filter,
    )

    # Ekspor maksimal 10.000 entri terbaru
    stmt = stmt.limit(10000)
    logs = (await session.execute(stmt)).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Header CSV
    writer.writerow([
        "ID",
        "Waktu (ISO)",
        "Pengguna",
        "Peran",
        "IP Address",
        "Aksi",
        "Detail",
        "Status",
        "Prev Hash",
        "Curr Hash",
    ])

    for log in logs:
        writer.writerow([
            log.id,
            log.created_at.isoformat() if log.created_at else "",
            log.actor_name,
            log.actor_role,
            log.ip_address or "",
            log.action,
            log.detail or "",
            log.status,
            log.prev_hash,
            log.curr_hash,
        ])

    csv_data = output.getvalue()
    output.close()

    filename = f"audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
        },
    )
