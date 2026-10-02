from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:3b"

    keycloak_internal_url: str = "http://keycloak:8080"  # untuk ambil JWKS (antar-container)
    keycloak_public_url: str = "http://localhost:8080"   # nilai `iss` di token
    keycloak_realm: str = "dev"


settings = Settings()
