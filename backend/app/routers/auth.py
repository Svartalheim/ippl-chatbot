"""
Router untuk autentikasi Keycloak
"""
import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..config import settings

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
async def login(req: LoginRequest):
    """
    Login menggunakan username dan password Keycloak.
    
    Mengembalikan access_token dan refresh_token yang dapat digunakan untuk autentikasi.
    
    **Cara menggunakan:**
    ```bash
    # Login dan simpan token
    TOKEN=$(curl -X POST http://localhost:8000/auth/login \\
      -H "Content-Type: application/json" \\
      -d '{"username":"dev","password":"dev"}' | jq -r .access_token)
    
    # Gunakan token untuk request lain
    curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/me
    ```
    """
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
                error_detail = response.json().get("error_description", "Login gagal")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Autentikasi gagal: {error_detail}",
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


@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token")
async def refresh_token(req: RefreshTokenRequest):
    """
    Refresh access token menggunakan refresh token.
    
    Access token biasanya expired dalam waktu singkat (default 5 menit).
    Gunakan refresh token untuk mendapatkan access token baru tanpa login ulang.
    
    **Contoh:**
    ```bash
    curl -X POST http://localhost:8000/auth/refresh \\
      -H "Content-Type: application/json" \\
      -d '{"refresh_token":"YOUR_REFRESH_TOKEN"}'
    ```
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
async def logout(req: LogoutRequest):
    """
    Logout dan revoke refresh token di Keycloak.
    
    Setelah logout, refresh token tidak bisa digunakan lagi.
    Access token akan tetap valid sampai expired (tidak bisa di-revoke).
    
    **Contoh:**
    ```bash
    curl -X POST http://localhost:8000/auth/logout \\
      -H "Content-Type: application/json" \\
      -d '{"refresh_token":"YOUR_REFRESH_TOKEN"}'
    ```
    """
    logout_url = f"{settings.keycloak_internal_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/logout"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                logout_url,
                data={
                    "client_id": settings.keycloak_client_id,
                    "refresh_token": req.refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )
            
            # Keycloak mengembalikan 204 jika berhasil
            if response.status_code not in (204, 200):
                # Tetap return success, karena token mungkin sudah expired
                pass
                
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Keycloak tidak dapat dihubungi: {str(e)}",
            )


@router.get("/introspect", summary="Introspect token (untuk debugging)")
async def introspect_token(token: str):
    """
    Introspect token untuk melihat informasi detail (berguna untuk debugging).
    
    **Contoh:**
    ```bash
    curl "http://localhost:8000/auth/introspect?token=YOUR_ACCESS_TOKEN"
    ```
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
