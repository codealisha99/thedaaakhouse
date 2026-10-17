"""Application settings — every configurable value comes from the environment.

See .env.example. The app must run with defaults for local dev
(SQLite fallback) and use Postgres when DATABASE_URL is set.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Known development-only JWT secret. Production must never accept this value.
DEV_JWT_SECRET = "dev-only-change-me"

#: Absolute directory containing this package's backend/ folder. Relative
#: paths resolve against it — never against os.getcwd().
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "thedaaakhouse"
    environment: str = "development"
    log_level: str = "INFO"

    # Comma-separated; MUST include every origin the frontend is served from.
    # (Audit finding: hardcoded :3000 broke the UI when it ran on :3100.)
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:3100"

    jwt_secret: str = DEV_JWT_SECRET
    jwt_expiry_min: int = 60 * 24 * 7

    # Local dev binds loopback only (port 8001 avoids the Sherlock :8000
    # collision). Override via env for Docker/prod (e.g. BACKEND_HOST=0.0.0.0).
    backend_host: str = "127.0.0.1"
    backend_port: int = 8001

    # Postgres in docker-compose; SQLite fallback for zero-dependency local dev.
    # Empty default => derived from data_dir (deterministic, cwd-independent).
    # Set DATABASE_URL explicitly to override (e.g. Postgres).
    database_url: str = ""

    # Resolved to an absolute path (see validator). Uploads + SQLite live here.
    data_dir: str = str(_BACKEND_DIR / "data")
    max_upload_mb: int = 10

    llm_provider: str = "ollama"  # "ollama" | "openai_compatible" | "grok"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    openai_compatible_base_url: str = "https://api.openai.com/v1"
    openai_compatible_api_key: str = ""
    openai_compatible_model: str = "gpt-4o-mini"

    # Grok (xAI) boundary — disabled placeholder. Nothing routes here.
    grok_enabled: bool = False
    grok_base_url: str = "https://api.x.ai/v1"
    grok_api_key: str = ""
    grok_model: str = "grok-3"

    embedding_provider: str = "local"
    embedding_dim: int = 384

    # Startup-search adapter for opportunity discovery ("none" = user-supplied
    # URLs only). Providers register in app/opportunities/providers.py.
    startup_search_provider: str = "none"

    # ---- Safe fetcher (backend/app/ingestion/safe_fetch.py) ----
    # One guard for every user-supplied URL (job import, company research).
    # Schemes fixed to http/https; ports/redirects/size bounded here.
    fetch_timeout_s: float = 20.0
    fetch_max_bytes: int = 1_000_000
    fetch_max_redirects: int = 5
    fetch_allowed_ports: str = "80,443"
    fetch_user_agent: str = "thedaaakhouse/0.3 (+safe-fetch)"

    # ---- Durable tasks (backend/app/workflows) ----
    # Redis/RQ is only the delivery bus; PostgreSQL task state is authoritative.
    # Empty => no Redis: the poll-mode worker + dispatcher still run everything.
    redis_url: str = ""
    redis_queue_name: str = "tasks"
    wf_max_attempts: int = 5
    wf_retry_base_s: float = 1.0
    wf_retry_jitter: float = 0.25  # 0..1 fraction added to deterministic backoff
    wf_lease_seconds: int = 300
    wf_dispatcher_interval_s: float = 1.0
    wf_poll_interval_s: float = 1.0
    wf_shutdown_grace_s: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def fetch_allowed_port_set(self) -> frozenset[int]:
        return frozenset(
            int(p.strip()) for p in self.fetch_allowed_ports.split(",") if p.strip()
        )

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @model_validator(mode="after")
    def _resolve_paths(self):
        # data_dir: relative values anchor at backend/, never cwd.
        d = Path(self.data_dir)
        if not d.is_absolute():
            d = _BACKEND_DIR / d
        object.__setattr__(self, "data_dir", str(d))
        # database_url: explicit value wins; otherwise SQLite inside data_dir.
        if not self.database_url:
            object.__setattr__(self, "database_url", f"sqlite:///{d}/thedaaakhouse.db")
        return self

    def ensure_production_ready(self) -> None:
        """Refuse to serve production traffic on unsafe defaults.

        Never prints the secret — only states which check failed.
        """
        if self.environment.strip().lower() != "production":
            return
        problems: list[str] = []
        if not self.jwt_secret or self.jwt_secret == DEV_JWT_SECRET:
            problems.append("JWT_SECRET is missing or still the development default")
        if problems:
            raise RuntimeError("refusing to start in production: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
