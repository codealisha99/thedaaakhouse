"""SQLAlchemy engine/session. Postgres when DATABASE_URL is postgres, else SQLite.

pgvector columns are only registered on Postgres; models degrade gracefully
on SQLite (vector fields stored as JSON) so tests/dev work without Docker.
"""

from collections.abc import Generator
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import DateTime, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Shared server-default timestamps; imported by every model module."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def uuid_key() -> str:
    """Shared primary-key generator so model modules avoid circular imports."""
    return str(uuid.uuid4())


def _connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _ensure_sqlite_parent(url: str) -> None:
    """SQLite won't create missing parent directories — do it here so any
    DATABASE_URL pointing at a fresh path boots cleanly."""
    if url.startswith("sqlite:") and ":memory:" not in url:
        path = url.split("sqlite:///")[-1].split("?")[0]
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)


settings = get_settings()
_ensure_sqlite_parent(settings.database_url)
engine = create_engine(settings.database_url, connect_args=_connect_args(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    # Import every model module so Base.metadata is fully populated.
    import app.db.models  # noqa: F401
    import app.workflows.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
