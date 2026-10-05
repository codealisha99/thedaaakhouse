"""Liveness + dependency status. Frontend polls this; deploy checks use it."""

from fastapi import APIRouter

from app.ai.providers import get_llm_provider
from app.core.config import get_settings

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
