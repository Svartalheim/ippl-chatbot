"""
Layanan Audit Log Imutabel dengan Rantai Hash SHA-256
Memenuhi standar integritas audit append-only dan verifikasi rantai hash kriptografis.
"""
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog

# Kunci advisory PostgreSQL untuk menserialkan penulisan audit_logs.
# Tanpa kunci ini, dua request bersamaan dapat membaca curr_hash terakhir yang sama
# sehingga rantai hash bercabang dan verify_audit_chain melaporkan kerusakan palsu.
AUDIT_CHAIN_LOCK_KEY = 7_771_001


async def record_audit_log(
    session: AsyncSession,
    actor_name: str,
    actor_role: str,
    action: str,
    detail: Optional[str],
    status: str,
    actor_user_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
    commit: bool = True,
) -> AuditLog:
    """
    Mencatat baris baru pada tabel audit_logs dengan rantai hash SHA-256.

    curr_hash = sha256(f"{prev_hash}|{timestamp_iso}|{actor_name}|{actor_role}|{action}|{detail}|{status}")
    """
    # 0. Kunci rantai hash sampai transaksi ini selesai (commit/rollback melepaskan kunci)
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": AUDIT_CHAIN_LOCK_KEY}
    )

    # 1. Ambil hash terakhir dari entri sebelumnya (atau 'GENESIS' jika masih kosong)
    stmt = select(AuditLog.curr_hash).order_by(AuditLog.id.desc()).limit(1)
    res = await session.execute(stmt)
    last_curr_hash = res.scalar_one_or_none()
    prev_hash = last_curr_hash if last_curr_hash is not None else "GENESIS"

    # 2. Waktu pembuatan dalam UTC dan format ISO 8601
    created_at = datetime.now(timezone.utc)
    timestamp_iso = created_at.isoformat()

    # 3. Hitung hash SHA-256
    detail_str = detail if detail is not None else ""
    payload = f"{prev_hash}|{timestamp_iso}|{actor_name}|{actor_role}|{action}|{detail_str}|{status}"
    curr_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # 4. Buat objek AuditLog
    log_entry = AuditLog(
        created_at=created_at,
        actor_user_id=actor_user_id,
        actor_name=actor_name,
        actor_role=actor_role,
        ip_address=ip_address,
        action=action,
        detail=detail,
        status=status,
        prev_hash=prev_hash,
        curr_hash=curr_hash,
    )
    session.add(log_entry)
    await session.flush()

    if commit:
        await session.commit()

    return log_entry


async def verify_audit_chain(session: AsyncSession) -> Dict[str, Any]:
    """
    Memvalidasi seluruh baris audit_logs dari awal hingga akhir.
    Memeriksa:
    1. prev_hash baris pertama adalah 'GENESIS'.
    2. prev_hash baris ke-N sama dengan curr_hash baris ke-(N-1).
    3. curr_hash baris ke-N sesuai dengan hasil perhitungan SHA-256 dari isinya.

    Mengembalikan:
        {
            "verified": bool,
            "total_entries": int,
            "checked_at": datetime,
            "broken_at_id": int | None
        }
    """
    checked_at = datetime.now(timezone.utc)
    stmt = select(AuditLog).order_by(AuditLog.id.asc())
    res = await session.execute(stmt)
    logs = res.scalars().all()

    total_entries = len(logs)
    if total_entries == 0:
        return {
            "verified": True,
            "total_entries": 0,
            "checked_at": checked_at,
            "broken_at_id": None,
        }

    expected_prev_hash = "GENESIS"

    for entry in logs:
        # Cek kontinuitas rantai prev_hash
        if entry.prev_hash != expected_prev_hash:
            return {
                "verified": False,
                "total_entries": total_entries,
                "checked_at": checked_at,
                "broken_at_id": entry.id,
            }

        # Format timestamp konsisten
        dt = entry.created_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        timestamp_iso = dt.isoformat()

        detail_str = entry.detail if entry.detail is not None else ""
        expected_curr_hash = hashlib.sha256(
            f"{entry.prev_hash}|{timestamp_iso}|{entry.actor_name}|{entry.actor_role}|{entry.action}|{detail_str}|{entry.status}".encode(
                "utf-8"
            )
        ).hexdigest()

        # Cek integritas curr_hash
        if entry.curr_hash != expected_curr_hash:
            return {
                "verified": False,
                "total_entries": total_entries,
                "checked_at": checked_at,
                "broken_at_id": entry.id,
            }

        expected_prev_hash = entry.curr_hash

    return {
        "verified": True,
        "total_entries": total_entries,
        "checked_at": checked_at,
        "broken_at_id": None,
    }
