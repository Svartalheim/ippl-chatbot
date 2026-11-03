"""
Modul autentikasi dan validasi JWT dengan Keycloak
Menyediakan sinkronisasi user ke basis data, verifikasi RBAC, dan dependency user.
"""
from datetime import datetime, timezone
from typing import List, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_session
from .models import Role, User

# Bearer token extractor
_bearer = HTTPBearer(auto_error=False)

# Keycloak JWKS client untuk validasi signature
_realm = settings.keycloak_realm
_jwks = jwt.PyJWKClient(
    f"{settings.keycloak_internal_url}/realms/{_realm}/protocol/openid-connect/certs",
    cache_keys=True,  # Cache public keys untuk performa
    max_cached_keys=16,
)
_issuer = f"{settings.keycloak_public_url}/realms/{_realm}"

KNOWN_ROLES = ["Admin", "Manajemen", "Finance", "HR", "Auditor", "Karyawan"]


class UserInfo:
    """Model informasi user dari JWT token dengan metadata RBAC basis data"""

    def __init__(self, token_data: dict):
        self._data = token_data
        self.db_user: Optional[User] = None
        self.db_id: Optional[str] = None
        self.role_name: str = "Karyawan"
        self.allowed_classifications: List[str] = ["Public"]

    @property
    def username(self) -> str:
        """Username dari Keycloak"""
        return self._data.get("preferred_username", "")

    @property
    def email(self) -> Optional[str]:
        """Email user"""
        return self._data.get("email")

    @property
    def first_name(self) -> Optional[str]:
        """Nama depan"""
        return self._data.get("given_name")

    @property
    def last_name(self) -> Optional[str]:
        """Nama belakang"""
        return self._data.get("family_name")

    @property
    def full_name(self) -> str:
        """Nama lengkap"""
        return self._data.get("name", self.username)

    @property
    def subject(self) -> str:
        """Subject ID (unique user ID dari Keycloak)"""
        return self._data.get("sub", "")

    @property
    def roles(self) -> list[str]:
        """Roles dari realm Keycloak"""
        realm_access = self._data.get("realm_access", {})
        return realm_access.get("roles", [])

    @property
    def client_roles(self) -> dict[str, list[str]]:
        """Roles per client"""
        return self._data.get("resource_access", {})

    @property
    def email_verified(self) -> bool:
        """Apakah email sudah diverifikasi"""
        return self._data.get("email_verified", False)

    @property
    def expires_at(self) -> Optional[datetime]:
        """Waktu expired token"""
        exp = self._data.get("exp")
        return datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None

    @property
    def issued_at(self) -> Optional[datetime]:
        """Waktu token diterbitkan"""
        iat = self._data.get("iat")
        return datetime.fromtimestamp(iat, tz=timezone.utc) if iat else None

    @property
    def raw(self) -> dict:
        """Raw token data untuk akses field custom"""
        return self._data

    def has_role(self, role: str) -> bool:
        """Check apakah user memiliki role tertentu"""
        return role in self.roles or self.role_name == role

    def has_client_role(self, client: str, role: str) -> bool:
        """Check apakah user memiliki role tertentu di client tertentu"""
        client_access = self.client_roles.get(client, {})
        return role in client_access.get("roles", [])

    def to_dict(self) -> dict:
        """Convert ke dictionary untuk response API"""
        return {
            "id": str(self.db_id) if self.db_id else None,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "subject": self.subject,
            "roles": self.roles,
            "role": self.role_name,
            "allowed_classifications": self.allowed_classifications,
            "email_verified": self.email_verified,
        }


def decode_token(token: str) -> dict:
    """
    Decode dan validasi JWT token dari Keycloak.
    """
    try:
        # Ambil public key dari JWKS endpoint
        key = _jwks.get_signing_key_from_jwt(token).key

        # Decode dan validasi token
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=_issuer,
            options={
                "verify_aud": False,  # Keycloak default aud = "account"
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": True,
            },
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sudah expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidIssuerError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token issuer tidak valid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token signature tidak valid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.DecodeError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token format tidak valid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token tidak valid: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def sync_user_to_db(session: AsyncSession, user_info: UserInfo) -> User:
    """
    Sinkronisasi pengguna dari klaim JWT ke tabel users dan mapping peran ke tabel roles.
    """
    # 1. Tentukan peran yang cocok
    matched_role_name = next(
        (r for r in KNOWN_ROLES if r in user_info.roles),
        "Karyawan",
    )

    role_stmt = select(Role).where(Role.name == matched_role_name)
    res_role = await session.execute(role_stmt)
    role = res_role.scalar_one_or_none()

    # 2. Cari atau buat user di basis data
    user_stmt = select(User).where(
        (User.keycloak_sub == user_info.subject) | (User.username == user_info.username)
    )
    res_user = await session.execute(user_stmt)
    user = res_user.scalar_one_or_none()

    now_utc = datetime.now(timezone.utc)

    if user is None:
        user = User(
            keycloak_sub=user_info.subject,
            username=user_info.username,
            full_name=user_info.full_name,
            email=user_info.email,
            role_id=role.id if role else None,
            is_active=True,
            last_login_at=now_utc,
        )
        session.add(user)
    else:
        user.keycloak_sub = user_info.subject
        user.username = user_info.username
        user.full_name = user_info.full_name
        user.email = user_info.email
        if role:
            user.role_id = role.id
        user.last_login_at = now_utc

    await session.commit()
    await session.refresh(user)

    # 3. Tempelkan informasi ke UserInfo
    user_info.db_user = user
    user_info.db_id = str(user.id)
    user_info.role_name = role.name if role else matched_role_name
    user_info.allowed_classifications = (
        role.allowed_classifications if role else ["Public"]
    )

    return user


async def get_user_allowed_classifications(
    session: AsyncSession, role_name: str
) -> List[str]:
    """
    Mengambil daftar allowed_classifications milik user dari tabel roles di basis data.
    """
    stmt = select(Role.allowed_classifications).where(Role.name == role_name)
    res = await session.execute(stmt)
    classifications = res.scalar_one_or_none()
    if classifications is not None:
        return classifications

    rbac_defaults = {
        "Karyawan": ["Public"],
        "HR": ["Public", "HR"],
        "Finance": ["Public", "Finance"],
        "Manajemen": ["Public", "HR", "Finance", "Confidential"],
        "Admin": ["Public"],
        "Auditor": [],
    }
    return rbac_defaults.get(role_name, ["Public"])


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> UserInfo:
    """
    Dependency untuk mendapatkan dan mensinkronkan user dari JWT token ke basis data.
    """
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak ada. Gunakan header: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(creds.credentials)
    user = UserInfo(payload)
    await sync_user_to_db(session, user)
    return user


async def optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> Optional[UserInfo]:
    """
    Dependency untuk mendapatkan user dari JWT token (optional).
    """
    if creds is None:
        return None

    try:
        payload = decode_token(creds.credentials)
        user = UserInfo(payload)
        await sync_user_to_db(session, user)
        return user
    except Exception:
        return None


def require_roles(*allowed_roles: str):
    """
    Helper dependency untuk memvalidasi user memiliki salah satu peran yang diizinkan.
    """
    async def role_checker(user: UserInfo = Depends(current_user)) -> UserInfo:
        user_roles = set(user.roles)
        if hasattr(user, "role_name") and user.role_name:
            user_roles.add(user.role_name)
        if not any(r in user_roles for r in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Akses ditolak. Endpoint ini memerlukan salah satu peran: {list(allowed_roles)}",
            )
        return user

    return role_checker


def require_role(role: str):
    """Kompatibilitas mundur untuk pengecekan peran tunggal"""
    return require_roles(role)
