.PHONY: init up down logs reset token

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
