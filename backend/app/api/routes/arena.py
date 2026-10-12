"""Interview Arena — drill/mock sessions with turns and evaluation."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import models
from app.db.database import get_db
from app.schemas.interview import ArenaAnswer, ArenaStart
from app.services import ArenaService

router = APIRouter(prefix="/api/arena", tags=["arena"])


@router.post("/sessions", status_code=201)
def start_session(payload: ArenaStart, db: Session = Depends(get_db),
                  user: models.User = Depends(get_current_user)):
    try:
        return ArenaService(db, user).start(
            payload.mode, difficulty=payload.difficulty,
            application_id=payload.application_id, resume_id=payload.resume_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions")
def list_sessions(application_id: str | None = None, db: Session = Depends(get_db),
                  user: models.User = Depends(get_current_user)):
    return ArenaService(db, user).list(application_id)


@router.get("/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db),
                user: models.User = Depends(get_current_user)):
    s = ArenaService(db, user).get(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    return s


@router.post("/sessions/{session_id}/answer")
def answer(session_id: str, payload: ArenaAnswer, db: Session = Depends(get_db),
           user: models.User = Depends(get_current_user)):
    try:
        return ArenaService(db, user).answer(session_id, payload.answer)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
