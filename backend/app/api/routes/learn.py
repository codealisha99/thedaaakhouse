"""Learning Hub — study plans and topic progress. All user-scoped."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import models
from app.db.database import get_db
from app.schemas.learn import AnswerIn, PlanCreate, TopicStatusIn
from app.services import LearningService

router = APIRouter(prefix="/api/learn", tags=["learn"])


@router.post("/plans", status_code=201)
def create_plan(payload: PlanCreate, db: Session = Depends(get_db),
                user: models.User = Depends(get_current_user)):
    try:
        return LearningService(db, user).create_plan(
            payload.application_id, resume_id=payload.resume_id, title=payload.title)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/plans")
def list_plans(application_id: str | None = None, db: Session = Depends(get_db),
               user: models.User = Depends(get_current_user)):
    return LearningService(db, user).list_plans(application_id)


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str, db: Session = Depends(get_db),
             user: models.User = Depends(get_current_user)):
    plan = LearningService(db, user).get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="study plan not found")
    return plan


@router.post("/plans/{plan_id}/answer")
def answer(plan_id: str, payload: AnswerIn, db: Session = Depends(get_db),
           user: models.User = Depends(get_current_user)):
    try:
        return LearningService(db, user).answer(plan_id, payload.topic, payload.answer)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/plans/{plan_id}/topics")
def set_topic_status(plan_id: str, payload: TopicStatusIn, db: Session = Depends(get_db),
                     user: models.User = Depends(get_current_user)):
    try:
        return LearningService(db, user).set_status(plan_id, payload.topic, payload.status)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
