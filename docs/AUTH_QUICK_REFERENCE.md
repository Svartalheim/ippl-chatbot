# Authentication Quick Reference Card

Quick cheat sheet untuk autentikasi Keycloak JWT di IPPL Chatbot.

---

## 🚀 Quick Start

```bash
# 1. Start services
make up

# 2. Test authentication
make test-quick

# 3. Full test suite
make test-auth
```

---

## 🔑 Default Credentials

```
Username: dev
Password: dev
API URL:  http://localhost:8000
Keycloak: http://localhost:8080 (admin/admin)
```

---

## 📡 API Endpoints

### Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"dev","password":"dev"}'
```

### Get User Info
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/me
```

### Chat
```bash
curl -X POST http://localhost:8000/llm/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello!"}'
```

### Refresh Token
```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"YOUR_REFRESH_TOKEN"}'
```

### Logout
```bash
curl -X POST http://localhost:8000/auth/logout \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"YOUR_REFRESH_TOKEN"}'
```

---

## 💻 Python Usage

```python
from app.auth import current_user, UserInfo, require_role
from fastapi import Depends

# Basic protected route
@app.get("/protected")
async def protected(user: UserInfo = Depends(current_user)):
    return {"username": user.username}

# Role-based access
@app.get("/admin", dependencies=[Depends(require_role("admin"))])
async def admin_only():
    return {"message": "Admin area"}

# Optional auth
from app.auth import optional_user

@app.get("/maybe-protected")
async def maybe_protected(user: UserInfo | None = Depends(optional_user)):
    return {"logged_in": user is not None}
```

---

## 🔐 UserInfo Properties

```python
user.username        # Username
user.email          # Email address
user.full_name      # Full name
user.first_name     # First name
user.last_name      # Last name
user.subject        # Unique user ID (sub)
user.roles          # List of realm roles
user.expires_at     # Token expiration datetime
user.has_role("x")  # Check if user has role
user.raw            # Raw JWT payload
user.to_dict()      # Convert to dict
```

---

## ⏱️ Token Lifetimes

```
Access Token:  5 minutes (300s)
Refresh Token: 30 minutes (1800s)
```

**Best Practice:** Refresh 1 minute before expiry

---

## 🧪 Testing Commands

```bash
# Quick health + login + user info
make test-quick

# Full authentication test suite
make test-auth

# Get token for manual testing
TOKEN=$(make -s token)

# Or using new login endpoint
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"dev","password":"dev"}' | jq -r .access_token)
```

---

## 📁 Client Examples

### Python
```bash
pip install httpx
python examples/python_client.py
```

### JavaScript
```bash
node examples/javascript_client.js
```

### Browser
```bash
open examples/browser_client.html
```

---

## ⚠️ Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Token tidak ada` | Missing Authorization header | Add `Authorization: Bearer <token>` |
| `Token sudah expired` | Access token expired | Use refresh token to get new one |
| `Token issuer tidak valid` | Wrong Keycloak URL config | Check `KEYCLOAK_PUBLIC_URL` in `.env` |
| `Keycloak tidak dapat dihubungi` | Keycloak service down | Run `docker compose restart keycloak` |

---

## 🔧 Configuration

### .env Variables
```env
KEYCLOAK_INTERNAL_URL=http://keycloak:8080
KEYCLOAK_PUBLIC_URL=http://localhost:8080
KEYCLOAK_REALM=dev
KEYCLOAK_CLIENT_ID=fastapi-app
```

### Change Token Lifetime
1. Open http://localhost:8080
2. Login: admin/admin
3. Select realm "dev"
4. Realm settings → Tokens
5. Adjust "Access Token Lifespan"

---

## 🔄 Auto-Refresh Pattern

```python
import httpx
from datetime import datetime, timedelta

class AuthClient:
    def __init__(self):
        self.access_token = None
        self.refresh_token = None
        self.expires_at = None
    
    async def ensure_valid(self):
        # Refresh if expires in < 1 min
        if datetime.now() >= (self.expires_at - timedelta(minutes=1)):
            await self.refresh()
    
    async def refresh(self):
        response = await httpx.post(
            "http://localhost:8000/auth/refresh",
            json={"refresh_token": self.refresh_token}
        )
        data = response.json()
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.expires_at = datetime.now() + timedelta(seconds=data["expires_in"])
```

---

## 📚 Documentation

- **Full Guide:** [docs/AUTHENTICATION.md](./AUTHENTICATION.md)
- **Implementation:** [docs/IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)
- **Examples:** [examples/README.md](../examples/README.md)
- **Dev Guide:** [README-dev-environment.md](../README-dev-environment.md)

---

## 🆘 Get Help

```bash
# View logs
docker compose logs -f backend keycloak

# Check services
docker compose ps

# Restart services
docker compose restart

# Full reset
make reset
make up
```

---

## ✅ Quick Checklist

Before deploying to production:

- [ ] Change default passwords
- [ ] Enable HTTPS
- [ ] Add CORS middleware
- [ ] Implement rate limiting
- [ ] Add audit logging
- [ ] Use secure cookies for web
- [ ] Backup Keycloak database
- [ ] Set proper token lifetimes
- [ ] Configure session timeouts
- [ ] Enable MFA (optional)

---

**Print this page for quick reference!** 📄
