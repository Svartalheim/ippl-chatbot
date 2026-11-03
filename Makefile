.PHONY: init up down logs reset token test-auth test-quick test test-security test-db test-perf reembed calibrate seed

PYTEST ?= $(shell if [ -f .venv/bin/pytest ]; then echo ".venv/bin/pytest"; else which pytest 2>/dev/null || echo "pytest"; fi)
PYTHON ?= $(shell if [ -f .venv/bin/python3 ]; then echo ".venv/bin/python3"; else which python3 2>/dev/null || echo "python3"; fi)
DOCKER_COMPOSE ?= $(shell if docker compose version >/dev/null 2>&1; then echo "docker compose"; elif which docker-compose >/dev/null 2>&1; then echo "docker-compose"; else echo "docker compose"; fi)

init:
	@test -f .env || cp .env.example .env
	@echo ".env siap."

check-daemon:
	@docker info >/dev/null 2>&1 || (echo "⚠️ Docker daemon belum aktif! Jika menggunakan Colima di macOS, jalankan 'colima start'." && exit 1)

up: init check-daemon
	$(DOCKER_COMPOSE) up -d --build

down:
	$(DOCKER_COMPOSE) down

logs:
	$(DOCKER_COMPOSE) logs -f backend keycloak

reset:
	$(DOCKER_COMPOSE) down -v

# Ambil access token user dev/dev
token:
	@curl -s -X POST http://localhost:8080/realms/dev/protocol/openid-connect/token \
	  -d grant_type=password -d client_id=fastapi-app -d username=dev -d password=dev \
	  | $(PYTHON) -c "import sys,json; print(json.load(sys.stdin)['access_token'])"

# Test autentikasi lengkap
test-auth:
	@./scripts/test-auth.sh

# Quick test: health check, login, dan get user info
test-quick:
	@echo "Testing health..."
	@curl -s http://localhost:8000/health | jq
	@echo "\nLogging in..."
	@TOKEN=$$(curl -s -X POST http://localhost:8000/auth/login \
	  -H "Content-Type: application/json" \
	  -d '{"username":"dev","password":"dev"}' | jq -r .access_token); \
	echo "Getting user info..."; \
	curl -s -H "Authorization: Bearer $$TOKEN" http://localhost:8000/me | jq

# Aktivitas 4a: Pengujian Unit per Modul (Auth, Ingestion, Retrieval, Generation)
test:
	@echo "Menjalankan Pengujian Unit per Modul (Aktivitas 4a)..."
	PYTHONPATH=. $(PYTEST) backend/tests/test_4a_unit_modules.py -v

# Aktivitas 4b: Uji Keamanan Otomatis (Kebocoran RBAC, Prompt Injection, Imutabilitas Audit Log)
test-security:
	@echo "Menjalankan Uji Keamanan Otomatis (Aktivitas 4b)..."
	PYTHONPATH=. $(PYTEST) backend/tests/test_4b_security.py backend/tests/test_4b_db_integration.py -v

# Aktivitas 4b (integrasi): imutabilitas audit_logs & rantai hash terhadap PostgreSQL asli (butuh 'make up')
test-db:
	@echo "Menjalankan uji integrasi database audit_logs (butuh stack Docker berjalan)..."
	PYTHONPATH=. $(PYTEST) backend/tests/test_4b_db_integration.py -v

# Aktivitas 4c: Uji Kinerja & Beban 500 Pengguna Konkuren (Target p95 < 5 detik)
test-perf:
	@echo "Menjalankan Uji Kinerja & Beban 500 Pengguna Aktif (Aktivitas 4c)..."
	PYTHONPATH=. $(PYTHON) scripts/load_test_4c.py --concurrency $(or $(CONCURRENCY),500) --requests $(or $(REQUESTS),500)

# Embed ulang chunk yang masih memakai vektor mock (mis. seed sebelum model embedding selesai di-pull)
reembed:
	$(DOCKER_COMPOSE) exec backend python -m app.reembed

# Tampilkan skor relevansi pertanyaan berlabel untuk memilih RAG_SIMILARITY_THRESHOLD
calibrate:
	$(DOCKER_COMPOSE) exec backend python -m app.calibrate_rag

# Seeding awal basis data (Peran, Akun Prototipe, Dokumen 4 Klasifikasi, Genesis Audit Log)
seed:
	@echo "Menjalankan seeding basis data..."
	@PYTHONPATH=. $(PYTHON) -m backend.app.seed 2>/dev/null || docker compose exec backend python -m app.seed
