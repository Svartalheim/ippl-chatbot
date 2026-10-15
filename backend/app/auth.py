"""
Modul autentikasi dan validasi JWT dengan Keycloak
"""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Optional
from datetime import datetime

from .config import settings

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


class UserInfo:
    """Model informasi user dari JWT token"""
    
    def __init__(self, token_data: dict):
        self._data = token_data
    
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
        """Roles dari realm"""
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
        return datetime.fromtimestamp(exp) if exp else None
    
    @property
    def issued_at(self) -> Optional[datetime]:
        """Waktu token diterbitkan"""
        iat = self._data.get("iat")
        return datetime.fromtimestamp(iat) if iat else None
    
    @property
    def raw(self) -> dict:
        """Raw token data untuk akses field custom"""
        return self._data
    
    def has_role(self, role: str) -> bool:
        """Check apakah user memiliki role tertentu"""
        return role in self.roles
    
    def has_client_role(self, client: str, role: str) -> bool:
        """Check apakah user memiliki role tertentu di client tertentu"""
        client_access = self.client_roles.get(client, {})
        return role in client_access.get("roles", [])
    
    def to_dict(self) -> dict:
        """Convert ke dictionary untuk response API"""
        return {
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "subject": self.subject,
            "roles": self.roles,
            "email_verified": self.email_verified,
        }


def decode_token(token: str) -> dict:
    """
    Decode dan validasi JWT token dari Keycloak.
    
    Args:
        token: JWT token string
        
    Returns:
        dict: Decoded token payload
        
    Raises:
        HTTPException: Jika token tidak valid
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
                "verify_aud": False,  # Keycloak default aud = "account", skip validasi
                "verify_exp": True,   # Validasi expiration
                "verify_iat": True,   # Validasi issued at
                "verify_nbf": True,   # Validasi not before
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


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> UserInfo:
    """
    Dependency untuk mendapatkan user dari JWT token.
    
    Gunakan sebagai parameter di route handler:
    ```python
    @app.get("/protected")
    async def protected_route(user: UserInfo = Depends(current_user)):
        return {"username": user.username}
    ```
    
    Returns:
        UserInfo: Informasi user dari token
        
    Raises:
        HTTPException 401: Jika token tidak ada atau tidak valid
    """
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak ada. Gunakan header: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_token(creds.credentials)
    return UserInfo(payload)


def optional_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Optional[UserInfo]:
    """
    Dependency untuk mendapatkan user dari JWT token (optional).
    
    Tidak raise exception jika token tidak ada. Berguna untuk endpoint
    yang bisa diakses dengan atau tanpa autentikasi.
    
    Returns:
        UserInfo | None: Informasi user dari token, atau None jika tidak ada token
    """
    if creds is None:
        return None
    
    try:
        payload = decode_token(creds.credentials)
        return UserInfo(payload)
    except HTTPException:
        return None


def require_role(role: str):
    """
    Dependency untuk memvalidasi user memiliki role tertentu.
    
    Contoh penggunaan:
    ```python
    @app.get("/admin", dependencies=[Depends(require_role("admin"))])
    async def admin_only():
        return {"message": "Admin area"}
    ```
    
    Args:
        role: Nama role yang diperlukan
    """
    def check_role(user: UserInfo = Depends(current_user)):
        if not user.has_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' diperlukan untuk mengakses endpoint ini",
            )
        return user
    return check_role
