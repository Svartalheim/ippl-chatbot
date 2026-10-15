.PHONY: init up down logs reset token test-auth test-quick

init:
	@test -f .env || cp .env.example .env
	@echo ".env siap."

up: init
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f backend keycloak

reset:
	docker compose down -v

# Ambil access token user dev/dev
token:
	@curl -s -X POST http://localhost:8080/realms/dev/protocol/openid-connect/token \
	  -d grant_type=password -d client_id=fastapi-app -d username=dev -d password=dev \
	  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"

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
