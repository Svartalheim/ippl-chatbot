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
```bash
curl localhost:8000/health
TOKEN=$(make -s token)
curl -H "Authorization: Bearer $TOKEN" localhost:8000/me
curl -X POST localhost:8000/llm/chat -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"prompt":"Halo, siapa kamu?"}'
```
User dev realm: `dev` / `dev` (client publik `fastapi-app`).

## Reset total
`make reset` (hapus semua volume, termasuk data DB & model Ollama).
