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

#: Absolute path of the Alembic migration scripts (backend/alembic).
_ALEMBIC_SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent / "alembic"


def _alembic_head(engine) -> str:
    """The single head revision of the checked-in migration graph."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config()
    cfg.set_main_option("script_location", str(_ALEMBIC_SCRIPT_DIR))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    if len(heads) != 1:
        raise RuntimeError(
            "alembic revision graph has multiple heads — resolve before starting: "
            f"{heads}"
        )
    return heads[0]


def require_migrated(engine) -> None:
    """PostgreSQL is the source of truth: it must be *migrated*, not created.

    create_all is never used for Postgres — an unmigrated or stale schema
    must stop startup, not silently drift. Applies only to the explicit
    engine passed in (tests may pass SQLite to exercise the gate itself).
    """
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if not insp.has_table("alembic_version"):
        raise RuntimeError(
            "refusing to start: PostgreSQL database is not migrated. "
            "Run `backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head` "
            "before starting the backend. create_all is not used for PostgreSQL."
        )
    with engine.connect() as conn:
        current = conn.execute(text("select version_num from alembic_version")).scalar()
    head = _alembic_head(engine)
    if current != head:
        raise RuntimeError(
            f"refusing to start: alembic revision {current} != head {head}. "
            "Apply pending migrations with `alembic -c backend/alembic.ini upgrade head` "
            "and verify the schema matches the current models."
        )


def init_db(engine=None, db_settings=None) -> None:
    """Start-time schema check. SQLite (dev/tests) uses create_all for a
    zero-setup experience; PostgreSQL requires explicitly applied Alembic
    migrations — schema changes must land as revisions, never via stamp."""
    eng = engine if engine is not None else globals()["engine"]
    s = db_settings if db_settings is not None else globals()["settings"]
    # Import every model module so Base.metadata is fully populated.
    import app.db.models  # noqa: F401
    import app.discovery.models  # noqa: F401
    import app.submissions.models  # noqa: F401
    import app.outreach.models  # noqa: F401
    import app.workflows.models  # noqa: F401

    if s.is_postgres:
        require_migrated(eng)
    else:
        Base.metadata.create_all(bind=eng)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
