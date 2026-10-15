"""Development-only fixtures. NEVER enabled in production.

Each action is idempotent per user and clearly labels seeded records as
fictional test data. Seeding touches jobs only — never resumes, never
other users' data.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db import models
from app.db.database import get_db
from app.fixtures import nexora
from app.services import ApplicationService

router = APIRouter(prefix="/api/dev", tags=["dev"])


def _dev_only() -> None:
    if get_settings().environment.strip().lower() == "production":
        raise HTTPException(status_code=404, detail="not found")


@router.post("/seed-nexora", status_code=201)
def seed_nexora(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _dev_only()
    existing = (
        db.query(models.Application)
        .filter_by(user_id=user.id, company=nexora.COMPANY)
        .order_by(models.Application.created_at.asc())
        .first()
    )
    if existing is not None:
        return {"seeded": False, "application_id": existing.id,
                "detail": "fictional Nexora job already present; not duplicated"}
    svc = ApplicationService(db, user)
    obj = svc.create(
        company=nexora.COMPANY,
        role=nexora.ROLE,
        location=nexora.LOCATION,
        raw_jd=nexora.JD_TEXT,
        status="saved",
        notes=f"{nexora.MARKER}. {nexora.SALARY_NOTE}. {nexora.EXPERIENCE_NOTE}.",
    )
    return {"seeded": True, "application_id": obj.id,
            "detail": "fictional test job created; no resumes touched"}
