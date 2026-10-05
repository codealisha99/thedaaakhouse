"""Liveness + readiness. Frontend polls this; deploy checks use it.

/health is liveness (always 200 if the process answers).
/ready verifies the database with a live query (no secrets exposed).
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.providers import get_llm_provider
from app.core.config import get_settings
from app.db.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    s = get_settings()
    llm = get_llm_provider()
    return {
        "status": "ok",
        "app": s.app_name,
        "environment": s.environment,
        "database": "postgres" if s.is_postgres else "sqlite",
        "llm": llm.health(),
    }


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    try:
        db.execute(text("SELECT 1"))
        return {"ready": True, "database": "postgres" if s.is_postgres else "sqlite"}
    except Exception as e:
        return {"ready": False, "error": f"database unreachable: {type(e).__name__}"}
