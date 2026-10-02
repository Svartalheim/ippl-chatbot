import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

_bearer = HTTPBearer(auto_error=False)
_realm = settings.keycloak_realm
_jwks = jwt.PyJWKClient(
    f"{settings.keycloak_internal_url}/realms/{_realm}/protocol/openid-connect/certs"
)
_issuer = f"{settings.keycloak_public_url}/realms/{_realm}"


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token tidak ada")
    try:
        key = _jwks.get_signing_key_from_jwt(creds.credentials).key
        return jwt.decode(
            creds.credentials,
            key,
            algorithms=["RS256"],
            issuer=_issuer,
            options={"verify_aud": False},  # Keycloak default aud = "account"
        )
    except Exception as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token tidak valid: {e}")
