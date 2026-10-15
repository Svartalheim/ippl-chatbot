# Dokumentasi Autentikasi

## Overview

Sistem autentikasi menggunakan **Keycloak** sebagai Identity Provider dengan **JWT (JSON Web Token)** untuk validasi.

### Flow Autentikasi

```
┌─────────┐         ┌──────────┐         ┌──────────┐
│ Client  │────1───▶│ FastAPI  │────2───▶│ Keycloak │
│         │         │          │         │          │
│         │◀───3────│          │◀───4────│          │
│         │  Token  │          │  Token  │          │
└─────────┘         └──────────┘         └──────────┘
     │
     └────5──────▶ Gunakan token untuk request berikutnya
```

1. Client kirim username & password ke `/auth/login`
2. FastAPI forward credentials ke Keycloak
3. Keycloak validate dan kirim JWT token
4. FastAPI teruskan token ke client
5. Client gunakan token di header `Authorization: Bearer <token>`

---

## Endpoints

### 1. Login

**POST** `/auth/login`

Login menggunakan username dan password untuk mendapatkan JWT token.

**Request:**
```json
{
  "username": "dev",
  "password": "dev"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 300,
  "refresh_expires_in": 1800
}
```

**Contoh cURL:**
```bash
# Login dan simpan access token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"dev","password":"dev"}' | jq -r .access_token)

# Login dan simpan semua token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"dev","password":"dev"}' > tokens.json
```

---

### 2. Refresh Token

**POST** `/auth/refresh`

Refresh access token yang sudah expired menggunakan refresh token.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 300,
  "refresh_expires_in": 1800
}
```

**Contoh cURL:**
```bash
# Ambil refresh token dari file
REFRESH_TOKEN=$(cat tokens.json | jq -r .refresh_token)

# Refresh dan dapatkan access token baru
NEW_TOKEN=$(curl -s -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}" | jq -r .access_token)
```

---

### 3. Logout

**POST** `/auth/logout`

Logout dan revoke refresh token. Access token akan tetap valid sampai expired.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:** `204 No Content`

**Contoh cURL:**
```bash
REFRESH_TOKEN=$(cat tokens.json | jq -r .refresh_token)

curl -X POST http://localhost:8000/auth/logout \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}"
```

---

### 4. Get Current User

**GET** `/me`

Mendapatkan informasi user yang sedang login dari JWT token.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "username": "dev",
  "email": "dev@example.com",
  "full_name": "Dev User",
  "first_name": "Dev",
  "last_name": "User",
  "subject": "a1b2c3d4-...",
  "roles": ["default-roles-dev", "offline_access", "uma_authorization"],
  "email_verified": true
}
```

**Contoh cURL:**
```bash
# Gunakan token yang sudah didapat
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/me
```

---

### 5. Introspect Token (Debug)

**GET** `/auth/introspect?token=<token>`

Introspect token untuk debugging dan melihat detail token.

**Response:**
```json
{
  "exp": 1704067200,
  "iat": 1704066900,
  "jti": "abc123...",
  "iss": "http://localhost:8080/realms/dev",
  "sub": "a1b2c3d4-...",
  "typ": "Bearer",
  "azp": "fastapi-app",
  "preferred_username": "dev",
  "email_verified": true,
  "email": "dev@example.com",
  "active": true
}
```

**Contoh cURL:**
```bash
curl "http://localhost:8000/auth/introspect?token=$TOKEN"
```

---

## Menggunakan JWT Token

### Di cURL

```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"dev","password":"dev"}' | jq -r .access_token)

# 2. Gunakan token untuk protected endpoints
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/me

# 3. Chat dengan LLM
curl -X POST http://localhost:8000/llm/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello, siapa kamu?"}'
```

### Di Python

```python
import httpx

# 1. Login
response = httpx.post("http://localhost:8000/auth/login", json={
    "username": "dev",
    "password": "dev"
})
tokens = response.json()
access_token = tokens["access_token"]

# 2. Gunakan token
headers = {"Authorization": f"Bearer {access_token}"}

# Get user info
user_info = httpx.get("http://localhost:8000/me", headers=headers).json()
print(f"Logged in as: {user_info['username']}")

# Chat with LLM
chat_response = httpx.post(
    "http://localhost:8000/llm/chat",
    headers=headers,
    json={"prompt": "Hello!"}
).json()
print(chat_response["answer"])
```

### Di JavaScript/TypeScript

```typescript
// 1. Login
const loginResponse = await fetch('http://localhost:8000/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'dev', password: 'dev' })
});
const { access_token } = await loginResponse.json();

// 2. Gunakan token
const headers = { 'Authorization': `Bearer ${access_token}` };

// Get user info
const userInfo = await fetch('http://localhost:8000/me', { headers })
  .then(r => r.json());
console.log('Logged in as:', userInfo.username);

// Chat with LLM
const chatResponse = await fetch('http://localhost:8000/llm/chat', {
  method: 'POST',
  headers: { ...headers, 'Content-Type': 'application/json' },
  body: JSON.stringify({ prompt: 'Hello!' })
}).then(r => r.json());
console.log(chatResponse.answer);
```

---

## Menggunakan di FastAPI Routes

### Basic Authentication

```python
from fastapi import Depends
from app.auth import current_user, UserInfo

@app.get("/protected")
async def protected_route(user: UserInfo = Depends(current_user)):
    return {
        "message": f"Hello {user.username}!",
        "email": user.email,
        "roles": user.roles
    }
```

### Optional Authentication

```python
from fastapi import Depends
from app.auth import optional_user, UserInfo

@app.get("/maybe-protected")
async def maybe_protected(user: UserInfo | None = Depends(optional_user)):
    if user:
        return {"message": f"Hello {user.username}!"}
    else:
        return {"message": "Hello anonymous!"}
```

### Role-Based Access Control

```python
from fastapi import Depends
from app.auth import require_role, UserInfo

# Hanya admin yang bisa akses
@app.get("/admin", dependencies=[Depends(require_role("admin"))])
async def admin_only():
    return {"message": "Admin area"}

# Atau dengan user info
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current: UserInfo = Depends(require_role("admin"))
):
    # current akan berisi user info jika role valid
    return {"deleted": user_id, "by": current.username}
```

### Check Role Manually

```python
from fastapi import Depends, HTTPException
from app.auth import current_user, UserInfo

@app.get("/moderator")
async def moderator_route(user: UserInfo = Depends(current_user)):
    if not user.has_role("moderator") and not user.has_role("admin"):
        raise HTTPException(403, "Moderator or admin role required")
    
    return {"message": "Welcome moderator!"}
```

---

## UserInfo Class

Class `UserInfo` menyediakan properties untuk mengakses informasi dari JWT token:

```python
class UserInfo:
    @property
    def username(self) -> str:
        """Username dari Keycloak"""
    
    @property
    def email(self) -> str | None:
        """Email user"""
    
    @property
    def full_name(self) -> str:
        """Nama lengkap"""
    
    @property
    def first_name(self) -> str | None:
        """Nama depan"""
    
    @property
    def last_name(self) -> str | None:
        """Nama belakang"""
    
    @property
    def subject(self) -> str:
        """Unique user ID dari Keycloak"""
    
    @property
    def roles(self) -> list[str]:
        """List of realm roles"""
    
    @property
    def client_roles(self) -> dict[str, list[str]]:
        """Roles per client"""
    
    @property
    def email_verified(self) -> bool:
        """Apakah email sudah diverifikasi"""
    
    @property
    def expires_at(self) -> datetime | None:
        """Waktu expired token"""
    
    @property
    def issued_at(self) -> datetime | None:
        """Waktu token diterbitkan"""
    
    @property
    def raw(self) -> dict:
        """Raw token data untuk custom fields"""
    
    def has_role(self, role: str) -> bool:
        """Check apakah user memiliki role tertentu"""
    
    def has_client_role(self, client: str, role: str) -> bool:
        """Check apakah user memiliki role di client tertentu"""
    
    def to_dict(self) -> dict:
        """Convert ke dictionary untuk API response"""
```

---

## Token Expiration

### Default Keycloak Settings

- **Access Token**: 5 menit (300 detik)
- **Refresh Token**: 30 menit (1800 detik)

### Best Practices

1. **Simpan refresh token** dengan aman (localStorage, secure cookie, dll)
2. **Implement token refresh** otomatis sebelum access token expired
3. **Handle 401 errors** dengan refresh token atau redirect ke login
4. **Logout** dengan revoke refresh token untuk security

### Auto-Refresh Pattern

```python
import httpx
from datetime import datetime, timedelta

class AuthClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None
        self.expires_at = None
    
    async def login(self, username: str, password: str):
        response = await httpx.post(f"{self.base_url}/auth/login", json={
            "username": username,
            "password": password
        })
        data = response.json()
        
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.expires_at = datetime.now() + timedelta(seconds=data["expires_in"])
    
    async def ensure_token_valid(self):
        """Refresh token jika akan expired dalam 1 menit"""
        if self.expires_at and datetime.now() > (self.expires_at - timedelta(minutes=1)):
            await self.refresh()
    
    async def refresh(self):
        response = await httpx.post(f"{self.base_url}/auth/refresh", json={
            "refresh_token": self.refresh_token
        })
        data = response.json()
        
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.expires_at = datetime.now() + timedelta(seconds=data["expires_in"])
    
    def get_headers(self):
        return {"Authorization": f"Bearer {self.access_token}"}

# Usage
client = AuthClient("http://localhost:8000")
await client.login("dev", "dev")

# Akan auto-refresh jika perlu
await client.ensure_token_valid()
response = await httpx.get(
    "http://localhost:8000/me",
    headers=client.get_headers()
)
```

---

## Keycloak Configuration

### Default User (Development)

- **Username**: `dev`
- **Password**: `dev`
- **Email**: `dev@example.com`
- **Realm**: `dev`
- **Client ID**: `fastapi-app`

### Keycloak Admin Console

- **URL**: http://localhost:8080
- **Username**: `admin`
- **Password**: `admin`

### Menambah User Baru

1. Buka Keycloak Admin Console
2. Pilih realm `dev`
3. Menu **Users** → **Add user**
4. Isi username, email, dll
5. Tab **Credentials** → Set password

### Menambah Roles

1. Menu **Realm roles** → **Create role**
2. Isi nama role (misal: `moderator`, `admin`)
3. Assign role ke user: **Users** → pilih user → **Role mapping**

---

## Security Considerations

### ✅ DO

- Gunakan HTTPS di production
- Simpan refresh token dengan aman
- Implement token rotation
- Set proper CORS settings
- Use secure cookies untuk web apps
- Logout dengan revoke refresh token

### ❌ DON'T

- Jangan simpan token di localStorage untuk sensitive apps (XSS vulnerable)
- Jangan hardcode credentials
- Jangan share token antara users
- Jangan skip token validation
- Jangan expose token di logs/URLs

---

## Troubleshooting

### Error: "Token tidak ada"

Pastikan header `Authorization: Bearer <token>` ada di request.

```bash
# ✅ Benar
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/me

# ❌ Salah - tidak ada header
curl http://localhost:8000/me
```

### Error: "Token sudah expired"

Access token sudah expired (default 5 menit). Gunakan refresh token:

```bash
NEW_TOKEN=$(curl -s -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}" | jq -r .access_token)
```

### Error: "Token issuer tidak valid"

Pastikan `KEYCLOAK_PUBLIC_URL` di `.env` sesuai dengan URL yang diakses client:

```env
# Jika akses dari localhost
KEYCLOAK_PUBLIC_URL=http://localhost:8080

# Jika deploy ke domain
KEYCLOAK_PUBLIC_URL=https://auth.yourdomain.com
```

### Error: "Keycloak tidak dapat dihubungi"

Pastikan service Keycloak running:

```bash
docker compose ps
docker compose logs keycloak
```

---

## Testing

### Manual Testing

```bash
# 1. Start services
docker compose up -d

# 2. Wait for Keycloak to start (check logs)
docker compose logs -f keycloak

# 3. Login
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"dev","password":"dev"}' | jq -r .access_token)

# 4. Test protected endpoint
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/me

# 5. Test chat
curl -X POST http://localhost:8000/llm/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Halo!"}'
```

### Automated Testing dengan pytest

```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_login():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/auth/login", json={
            "username": "dev",
            "password": "dev"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

@pytest.mark.asyncio
async def test_protected_endpoint_without_token():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/me")
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_protected_endpoint_with_token():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Login first
        login_resp = await client.post("/auth/login", json={
            "username": "dev",
            "password": "dev"
        })
        token = login_resp.json()["access_token"]
        
        # Use token
        response = await client.get(
            "/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "dev"
```

---

## API Documentation

Setelah aplikasi running, buka:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

Di Swagger UI, klik tombol **Authorize** dan masukkan token untuk testing endpoints.
