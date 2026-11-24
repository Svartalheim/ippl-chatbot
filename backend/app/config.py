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
    # Kredensial admin Keycloak (master realm) untuk mengakhiri sesi pengguna (FR-AUTH-005)
    keycloak_admin: str = "admin"
    keycloak_admin_password: str = "admin"

    # Batas input kueri (FR-QUERY-005): kueri lebih panjang dipotong, bukan ditolak
    max_query_chars: int = 2000
    # Panjang maksimal teks kueri yang disimpan di log audit (setelah PII disamarkan)
    audit_query_max_chars: int = 1000

    # Retensi log audit (NFR-SEC-018), dijalankan via: python -m app.audit_retention
    audit_retention_days: int = 365
    audit_archive_dir: str = "/code/data/audit_archive"

    # Peringatan keamanan (FR-AUTH-005)
    security_alert_threshold: int = 5          # jumlah kejadian dalam jendela waktu
    security_alert_window_minutes: int = 10
    security_auto_terminate: bool = False      # akhiri sesi otomatis saat peringatan muncul

    # Endpoint debug (/auth/introspect) - matikan di produksi
    enable_debug_endpoints: bool = True

    # Validasi unggahan (NFR-SEC-006 / NFR-SEC-013)
    max_upload_mb: int = 20


settings = Settings()
