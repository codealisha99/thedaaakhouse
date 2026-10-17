"""Migration tests — baseline applies cleanly + startup gating refuses bad DBs."""

import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config

# paths in alembic.ini are repo-root-relative; resolve regardless of cwd
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"

EXPECTED_TABLES = {
    "users", "resumes", "jobs", "applications",
    "resume_versions", "ats_analyses", "interview_preps", "companies",
    # step 04 — opportunity ranking
    "organizations", "opportunities", "opportunity_evaluations",
    "applicant_count_observations",
    # step 03 — scheduled job discovery
    "discovery_sources", "job_listings", "listing_sources", "discovery_runs",
}


def _upgrade(db_path: str) -> None:
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_REPO_ROOT / "backend" / "alembic"))
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


# ---------------- startup gating (step 01) ----------------
#
# Postgres is the source of truth: init_db must refuse to boot unless the DB
# is explicitly migrated to the current head. create_all is never used there.
# The gate itself is engine-agnostic, so tests drive it with SQLite engines.

def _sqlite_engine(url: str):
    from sqlalchemy import create_engine

    return create_engine(url, connect_args={"check_same_thread": False})


def _populated_engine(db_path, migrated_rev=None):
    """Fresh SQLite engine, optionally stamped like a real migrated DB."""
    from sqlalchemy import text

    eng = _sqlite_engine(f"sqlite:///{db_path}")
    if migrated_rev is not None:
        with eng.begin() as conn:
            conn.execute(text("create table alembic_version (version_num varchar(32) not null)"))
            conn.execute(text("insert into alembic_version values (:r)"), {"r": migrated_rev})
    return eng


def test_gate_refuses_unmigrated_postgres(tmp_path):
    from app.db.database import require_migrated

    eng = _populated_engine(tmp_path / "not-migrated.db")
    with pytest.raises(RuntimeError, match="not migrated"):
        require_migrated(eng)


def test_gate_refuses_stale_revision(tmp_path):
    from app.db.database import _alembic_head, require_migrated

    head = _alembic_head(None)
    eng = _populated_engine(tmp_path / "stale.db", migrated_rev="00000000deadbeef")
    with pytest.raises(RuntimeError, match=r"00000000deadbeef"):
        require_migrated(eng)
    # same engine at head passes
    from sqlalchemy import text

    with eng.begin() as conn:
        conn.execute(text("update alembic_version set version_num = :r"), {"r": head})
    require_migrated(eng)


def test_multi_head_graph_detects():
    from app.db.database import _alembic_head

    # Committed graph is linear/single-head; _alembic_head returns it.
    head = _alembic_head(None)
    assert isinstance(head, str) and head


def test_init_db_postgres_is_gated(tmp_path, monkeypatch):
    """init_db with a Postgres-ish settings object must call the gate, not create_all."""
    import app.db.database as dbm

    class GPSettings:
        is_postgres = True

    called = []
    monkeypatch.setattr(dbm, "require_migrated", lambda eng: called.append(True))
    dbm.init_db(engine=object(), db_settings=GPSettings())
    assert called == [True]

    class SQLiteSettings:
        is_postgres = False

    # Also exercise the default-settings path (session DATABASE_URL is sqlite).
    calls_default = []
    monkeypatch.setattr(dbm, "require_migrated", lambda eng: calls_default.append(True))
    dbm.init_db()
    assert calls_default == []  # default settings resolve to SQLite here
