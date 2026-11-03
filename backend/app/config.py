from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://app_user:app_password@localhost:5432/app_db"
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_embed_model: str = "nomic-embed-text"
    allow_mock_embedding: bool = False

    # RAG retrieval — kalibrasi dengan: docker compose exec backend python -m app.calibrate_rag
    rag_top_k: int = 4
    rag_similarity_threshold: float = 0.55   # skor kosinus minimum agar chunk dianggap relevan
    rag_relative_margin: float = 0.08        # buang chunk yang jauh di bawah skor terbaik
    ollama_chat_timeout: float = 90.0

    keycloak_internal_url: str = "http://keycloak:8080"  # untuk ambil JWKS (antar-container)
    keycloak_public_url: str = "http://localhost:8080"   # nilai `iss` di token
    keycloak_realm: str = "dev"
    keycloak_client_id: str = "fastapi-app"


settings = Settings()
