"""
Peringatan keamanan & pengakhiran sesi (FR-AUTH-005).

- check_security_alert: jika satu aktor memicu kejadian berisiko (LOGIN_FAILED,
  PROMPT_INJECTION, QUERY_DENIED) >= ambang dalam jendela waktu, catat SECURITY_ALERT
  (sekali per jendela) dan opsional akhiri sesinya.
- terminate_user_sessions: logout semua sesi pengguna di Keycloak dan tandai
  sessions_revoked_at agar access token lama langsung ditolak backend.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import AuditLog, User
from .audit_service import record_audit_log

logger = logging.getLogger(__name__)

RISKY_ACTIONS = ("LOGIN_FAILED", "PROMPT_INJECTION", "QUERY_DENIED")


async def check_security_alert(
    session: AsyncSession,
    actor_name: str,
    actor_role: str,
    action: str,
    actor_user_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
) -> bool:
    """
    Kembalikan True jika SECURITY_ALERT baru dicatat. Kegagalan pemeriksaan tidak
    boleh menggagalkan permintaan pengguna, sehingga error hanya dicatat di log.
    """
    if action not in RISKY_ACTIONS:
        return False
    try:
        return await _check_security_alert(
            session, actor_name, actor_role, actor_user_id, ip_address
        )
    except Exception as e:
        logger.error("Pemeriksaan peringatan keamanan gagal: %s", e)
        return False


async def _check_security_alert(
    session: AsyncSession,
    actor_name: str,
    actor_role: str,
    actor_user_id: Optional[uuid.UUID],
    ip_address: Optional[str],
) -> bool:

    since = datetime.now(timezone.utc) - timedelta(minutes=settings.security_alert_window_minutes)
    count = (
        await session.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.actor_name == actor_name,
                AuditLog.action.in_(RISKY_ACTIONS),
                AuditLog.created_at >= since,
            )
        )
    ).scalar_one()
    if count < settings.security_alert_threshold:
        return False

    already = (
        await session.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.actor_name == actor_name,
                AuditLog.action == "SECURITY_ALERT",
                AuditLog.created_at >= since,
            )
        )
    ).scalar_one()
    if already:
        return False

    terminated = False
    if settings.security_auto_terminate and actor_user_id:
        user = await session.get(User, actor_user_id)
        if user is not None:
            terminated = await terminate_user_sessions(session, user)

    await record_audit_log(
        session=session,
        actor_name=actor_name,
        actor_role=actor_role,
        action="SECURITY_ALERT",
        detail=(
            f"{count} kejadian berisiko ({', '.join(RISKY_ACTIONS)}) dalam "
            f"{settings.security_alert_window_minutes} menit"
            + ("; sesi diakhiri otomatis" if terminated else "")
        ),
        status="Diblokir",
        actor_user_id=actor_user_id,
        ip_address=ip_address,
    )
    logger.warning("SECURITY_ALERT untuk aktor '%s' (%d kejadian)", actor_name, count)
    return True


async def _keycloak_admin_token(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        f"{settings.keycloak_internal_url}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": settings.keycloak_admin,
            "password": settings.keycloak_admin_password,
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def terminate_user_sessions(session: AsyncSession, user: User) -> bool:
    """
    Akhiri semua sesi pengguna. Penandaan sessions_revoked_at selalu dilakukan
    (berlaku walau Keycloak tidak dapat dihubungi); kembalikan True jika
    logout di Keycloak juga berhasil.
    """
    user.sessions_revoked_at = datetime.now(timezone.utc)
    await session.flush()

    try:
        async with httpx.AsyncClient() as client:
            token = await _keycloak_admin_token(client)
            resp = await client.post(
                f"{settings.keycloak_internal_url}/admin/realms/{settings.keycloak_realm}"
                f"/users/{user.keycloak_sub}/logout",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            resp.raise_for_status()
        return True
    except Exception as e:  # Keycloak tidak tersedia: token lama tetap ditolak backend
        logger.error("Gagal logout sesi Keycloak untuk %s: %s", user.username, e)
        return False
