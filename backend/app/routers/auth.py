"""
Router untuk autentikasi Keycloak dengan pencatatan audit log & sinkronisasi pengguna.
"""
from typing import Optional
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import UserInfo, current_user, decode_token, optional_user, sync_user_to_db
from ..config import settings
from ..db import get_session
from ..services.audit_service import record_audit_log

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Username Keycloak")
    password: str = Field(..., min_length=1, description="Password")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token dari login sebelumnya")


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token yang akan di-revoke")


def _keycloak_token_url() -> str:
    """URL endpoint token Keycloak"""
    return f"{settings.keycloak_internal_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/token"


@router.post("/login", response_model=TokenResponse, summary="Login dengan Keycloak")
async def login(
    req: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    Login menggunakan username dan password Keycloak.
    Mencatat event LOGIN atau LOGIN_FAILED ke tabel audit_logs.
    """
    client_ip = request.client.host if request.client else None

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                _keycloak_token_url(),
                data={
                    "grant_type": "password",
                    "client_id": settings.keycloak_client_id,
                    "username": req.username,
                    "password": req.password,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )

            if response.status_code != 200:
                error_detail = response.json().get("error_description", "Kredensial tidak valid")
                await record_audit_log(
                    session=session,
                    actor_name=req.username,
                    actor_role="Unknown",
                    action="LOGIN_FAILED",
                    detail=f"Login gagal untuk username '{req.username}': {error_detail}",
                    status="Gagal",
                    actor_user_id=None,
                    ip_address=client_ip,
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Autentikasi gagal: {error_detail}",
                )

            data = response.json()
            access_token = data["access_token"]

            # Sinkronisasi user & catat audit log
            actor_user_id: Optional[uuid.UUID] = None
            actor_name = req.username
            actor_role = "Karyawan"

            try:
                payload = decode_token(access_token)
                user_info = UserInfo(payload)
                db_user = await sync_user_to_db(session, user_info)
                actor_user_id = db_user.id
                actor_name = user_info.full_name or user_info.username
                actor_role = getattr(user_info, "role_name", "Karyawan")
            except Exception:
                pass

            await record_audit_log(
                session=session,
                actor_name=actor_name,
                actor_role=actor_role,
                action="LOGIN",
                detail=f"Login berhasil via Keycloak untuk pengguna '{req.username}'",
                status="Berhasil",
                actor_user_id=actor_user_id,
                ip_address=client_ip,
            )

            return TokenResponse(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_in=data["expires_in"],
                refresh_expires_in=data["refresh_expires_in"],
            )

        except httpx.RequestError as e:
            await record_audit_log(
                session=session,
                actor_name=req.username,
                actor_role="Unknown",
                action="LOGIN_FAILED",
                detail=f"Keycloak tidak dapat dihubungi: {str(e)}",
                status="Gagal",
                actor_user_id=None,
                ip_address=client_ip,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Keycloak tidak dapat dihubungi: {str(e)}",
            )


@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token")
async def refresh_token(req: RefreshTokenRequest):
    """
    Refresh access token menggunakan refresh token.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                _keycloak_token_url(),
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.keycloak_client_id,
                    "refresh_token": req.refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token tidak valid atau sudah expired",
                )

            data = response.json()
            return TokenResponse(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_in=data["expires_in"],
                refresh_expires_in=data["refresh_expires_in"],
            )

        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Keycloak tidak dapat dihubungi: {str(e)}",
            )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Logout dan revoke token")
async def logout(
    req: LogoutRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: Optional[UserInfo] = Depends(optional_user),
):
    """
    Logout dan revoke refresh token di Keycloak serta catat event LOGOUT ke audit_logs.
    """
    logout_url = f"{settings.keycloak_internal_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/logout"
    client_ip = request.client.host if request.client else None

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                logout_url,
                data={
                    "client_id": settings.keycloak_client_id,
                    "refresh_token": req.refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )
        except httpx.RequestError:
            pass

    # Catat audit log LOGOUT
    actor_name = user.full_name if user else "Pengguna"
    actor_role = getattr(
        user, "role_name", user.roles[0] if (user and user.roles) else "Karyawan"
    )
    actor_id: Optional[uuid.UUID] = (
        uuid.UUID(user.db_id) if (user and user.db_id) else None
    )

    await record_audit_log(
        session=session,
        actor_name=actor_name,
        actor_role=actor_role,
        action="LOGOUT",
        detail="Sesi pengguna dicabut dan logout berhasil",
        status="Berhasil",
        actor_user_id=actor_id,
        ip_address=client_ip,
    )


@router.get("/userinfo", summary="Mendapatkan informasi user aktif")
async def userinfo(user: UserInfo = Depends(current_user)):
    """
    Mendapatkan profil pengguna aktif yang diautentikasi dengan token JWT.
    """
    return user.to_dict()


@router.get("/introspect", summary="Introspect token (untuk debugging)")
async def introspect_token(token: str):
    """
    Introspect token untuk melihat informasi detail (berguna untuk debugging).
    """
    introspect_url = f"{settings.keycloak_internal_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/token/introspect"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                introspect_url,
                data={
                    "client_id": settings.keycloak_client_id,
                    "token": token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tidak dapat introspect token",
                )

            return response.json()

        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Keycloak tidak dapat dihubungi: {str(e)}",
            )
