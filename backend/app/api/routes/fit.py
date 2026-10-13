"""Career-fit evaluation: classify, explain, override, compare."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import models
from app.db.database import get_db
from app.schemas.profile import FitWeights, OverrideIn
from app.services import FitService

router = APIRouter(prefix="/api/fit", tags=["fit"])


class EvaluateIn(BaseModel):
    application_id: str
    weights: dict | None = None


class CompareIn(BaseModel):
    application_ids: list[str] = []


@router.post("/evaluate", status_code=201)
def evaluate(payload: EvaluateIn, db: Session = Depends(get_db),
             user: models.User = Depends(get_current_user)):
    try:
        return FitService(db, user).evaluate(payload.application_id, payload.weights)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/weights")
def default_weights():
    return FitWeights().model_dump()


@router.get("/history/{application_id}")
def history(application_id: str, db: Session = Depends(get_db),
            user: models.User = Depends(get_current_user)):
    try:
        return FitService(db, user).history(application_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/evaluations/{evaluation_id}")
def override(evaluation_id: str, payload: OverrideIn, db: Session = Depends(get_db),
             user: models.User = Depends(get_current_user)):
    try:
        return FitService(db, user).override(evaluation_id, payload.classification)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/compare")
def compare(payload: CompareIn, db: Session = Depends(get_db),
            user: models.User = Depends(get_current_user)):
    return FitService(db, user).compare(payload.application_ids)
