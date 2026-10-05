"""Shared FastAPI dependencies (DB session, services, auth)."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.ai.providers import get_llm_provider
from app.ai.providers.base import LLMProvider
from app.core.config import get_settings
from app.core.security import decode_token
from app.db import models
from app.db.database import get_db
from app.services import JobService, ResumeService

_bearer = HTTPBearer(auto_error=False)


def get_resume_service(db: Session = Depends(get_db)) -> ResumeService:
    return ResumeService(db)


def get_job_service(db: Session = Depends(get_db)) -> JobService:
    return JobService(db)


def get_llm() -> LLMProvider:
    return get_llm_provider()


def get_current_user(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> models.User:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated. Log in to access your data.")
    try:
        user_id = decode_token(creds.credentials, get_settings().jwt_secret)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid session: {e}. Log in again.")
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Account no longer exists.")
    return user
