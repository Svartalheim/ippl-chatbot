# Dev Stack: FastAPI + PostgreSQL + Ollama + Keycloak

## Quick start
```bash
make up          # salin .env.example -> .env, build & jalankan semua service
make logs        # pantau log
```
Pull model Ollama berjalan di container `ollama-pull` (pertama kali bisa beberapa menit).

| Service   | URL                          | Catatan                         |
|-----------|------------------------------|---------------------------------|
| API docs  | http://localhost:8000/docs   | FastAPI (hot reload)            |
| Keycloak  | http://localhost:8080        | admin / admin                   |
| Postgres  | localhost:5432               | user/pass di `.env`             |
| Ollama    | http://localhost:11434       |                                 |

## Tes alur

### 1. Manual dengan cURL
```bash
# Health check (tidak perlu autentikasi)
curl localhost:8000/health

# Login dan simpan token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"dev","password":"dev"}' | jq -r .access_token)

# Get user info
curl -H "Authorization: Bearer $TOKEN" localhost:8000/me | jq

# Chat dengan LLM
curl -X POST localhost:8000/llm/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Halo, siapa kamu?"}' | jq
```

### 2. Automated testing
```bash
# Run comprehensive auth tests
./scripts/test-auth.sh

# Atau dengan custom URL/credentials
BASE_URL=http://localhost:8000 USERNAME=dev PASSWORD=dev ./scripts/test-auth.sh
```

### 3. Python client
```bash
# Install httpx
pip install httpx

# Run example
python examples/python_client.py
```

### 4. JavaScript client
```bash
# Run example (Node.js)
node examples/javascript_client.js
```

**User default:** `dev` / `dev` (client publik `fastapi-app`)

## Dokumentasi Lengkap

📚 **Autentikasi & JWT**: Lihat [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) untuk:
- Flow autentikasi lengkap
- Semua endpoints autentikasi
- Cara menggunakan token
- Role-based access control
- Auto-refresh pattern
- Troubleshooting

## Reset total
`make reset` (hapus semua volume, termasuk data DB & model Ollama).
