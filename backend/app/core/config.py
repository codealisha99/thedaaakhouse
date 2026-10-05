"""Application settings — every configurable value comes from the environment.

See .env.example. The app must run with defaults for local dev
(SQLite fallback) and use Postgres when DATABASE_URL is set.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "darkhouse"
    environment: str = "development"
    log_level: str = "INFO"

    # Comma-separated; MUST include every origin the frontend is served from.
    # (Audit finding: hardcoded :3000 broke the UI when it ran on :3100.)
    cors_origins: str = "http://localhost:3000,http://localhost:3100"

    jwt_secret: str = "dev-only-change-me"
    jwt_expiry_min: int = 60 * 24 * 7

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # Postgres in docker-compose; SQLite fallback for zero-dependency local dev.
    database_url: str = "sqlite:///./data/thedaaakhouse.db"

    data_dir: str = "./data"
    max_upload_mb: int = 10

    llm_provider: str = "ollama"  # "ollama" | "openai_compatible"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    openai_compatible_base_url: str = "https://api.openai.com/v1"
    openai_compatible_api_key: str = ""
    openai_compatible_model: str = "gpt-4o-mini"

    embedding_provider: str = "local"
    embedding_dim: int = 384

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
