"""Config/path determinism tests."""


def test_data_dir_and_db_independent_of_cwd(tmp_path, monkeypatch):
    from app.core.config import _BACKEND_DIR, get_settings

    for var in ("DATABASE_URL", "DATA_DIR"):
        monkeypatch.delenv(var, raising=False)
    get_settings.cache_clear()
    try:
        monkeypatch.chdir(tmp_path)  # simulate running from anywhere
        s = get_settings()
        assert s.data_dir == str(_BACKEND_DIR / "data")
        assert s.database_url == f"sqlite:///{_BACKEND_DIR / 'data'}/thedaaakhouse.db"
    finally:
        get_settings.cache_clear()


def test_explicit_database_url_respected(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@h/db")
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert s.database_url == "postgresql+psycopg2://u:p@h/db"
        assert s.is_postgres
    finally:
        get_settings.cache_clear()
