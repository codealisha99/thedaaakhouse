"""Pytest fixtures — every test gets an isolated SQLite DB."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    from app.core.config import get_settings

    get_settings.cache_clear()

    import app.db.models  # noqa: F401 — register tables

    eng = create_engine(url, connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=eng)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers(client):
    """Register a fresh user; return Authorization headers."""
    r = client.post("/api/auth/register", json={"username": "tester", "password": "password123"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def sample_jd():
    return (
        "Senior AI Engineer at Acme. You will build RAG pipelines and LLM agents. "
        "Requirements: 3+ years Python, FastAPI, vector databases (pgvector), Docker, "
        "Kubernetes, AWS. Nice to have: Go, Terraform."
    )


@pytest.fixture()
def sample_resume():
    return (
        "Jane Doe\njane@example.com\n555-0100\n\nEXPERIENCE\n"
        "Senior Engineer, Beta Corp, 2020-2025\n"
        "- Built RAG pipelines with Python and FastAPI serving 10k users\n"
        "- Implemented vector retrieval using pgvector and Docker\n"
        "- Shipped LLM agents to production\n\n"
        "EDUCATION\nBS Computer Science, 2016-2020\n\nSKILLS\nPython, FastAPI, Docker, SQL"
    )
