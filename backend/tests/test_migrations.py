"""Migration tests — baseline applies cleanly to a fresh database."""

import sqlite3

from alembic.config import Config

EXPECTED_TABLES = {
    "users", "resumes", "jobs", "applications",
    "resume_versions", "ats_analyses", "interview_preps", "companies",
}


def _upgrade(db_path: str) -> None:
    cfg = Config("backend/alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    from alembic import command

    command.upgrade(cfg, "head")


def test_baseline_creates_all_tables(tmp_path):
    db = tmp_path / "fresh.db"
    _upgrade(str(db))
    tables = {
        r[0]
        for r in sqlite3.connect(db).execute("select name from sqlite_master where type='table'")
    }
    assert EXPECTED_TABLES <= tables


def test_metadata_matches_baseline():
    from app.db.database import Base

    assert EXPECTED_TABLES <= set(Base.metadata.tables)
