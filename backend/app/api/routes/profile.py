"""Career profile — one row per user. Demonstrated vs claimed stay distinct."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import models
from app.db.database import get_db
from app.schemas.profile import CareerProfileIn, SeedIn
from app.services import ProfileService

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("")
def get_profile(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return ProfileService(db, user).get()


@router.put("")
def update_profile(payload: CareerProfileIn, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    return ProfileService(db, user).update(payload.model_dump())


@router.post("/seed")
def seed_profile(payload: SeedIn, db: Session = Depends(get_db),
                 user: models.User = Depends(get_current_user)):
    try:
        return ProfileService(db, user).seed_from_resume(payload.resume_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
