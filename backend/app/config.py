from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://app_user:app_password@localhost:5432/app_db"
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_embed_model: str = "nomic-embed-text"
    allow_mock_embedding: bool = False

    keycloak_internal_url: str = "http://keycloak:8080"  # untuk ambil JWKS (antar-container)
    keycloak_public_url: str = "http://localhost:8080"   # nilai `iss` di token
    keycloak_realm: str = "dev"
    keycloak_client_id: str = "fastapi-app"


settings = Settings()
