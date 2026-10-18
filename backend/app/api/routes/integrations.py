"""Integrations status — which providers exist and which are live."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.ai.providers import provider_status
from app.api.dependencies import get_current_user
from app.db import models
from app.db.database import get_db
from app.core.config import get_settings
from app.outreach.delivery_models import EmailAccount
from app.outreach.gmail import GmailError, begin_oauth, complete_oauth, disconnect, sync_replies

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("")
def list_integrations(user: models.User = Depends(get_current_user)):
    _ = user
    return {"providers": provider_status()}


@router.get("/gmail")
def gmail_status(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    account = db.query(EmailAccount).filter_by(user_id=user.id).first()
    return {"provider": "gmail", "enabled": get_settings().gmail_enabled,
            "connected": bool(account and account.status == "connected"),
            "email": account.email if account and account.status == "connected" else None,
            "capabilities": ["send", "poll_replies"] if account and account.status == "connected" else []}


@router.post("/gmail/connect")
def gmail_connect(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    try: return {"authorization_url": begin_oauth(db, user.id)}
    except GmailError as exc: raise HTTPException(503, detail=str(exc)) from None


@router.get("/gmail/callback")
def gmail_callback(state: str = Query(...), code: str = Query(...), error: str | None = None,
                   db: Session = Depends(get_db)):
    if error: raise HTTPException(400, detail="Google OAuth was not completed")
    try:
        email = complete_oauth(db, state, code)
        return {"connected": True, "provider": "gmail", "email": email}
    except GmailError as exc: raise HTTPException(400, detail=str(exc)) from None


@router.delete("/gmail")
def gmail_disconnect(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return {"disconnected": disconnect(db, user.id)}


@router.post("/gmail/sync")
def gmail_sync(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    try: return {"events_added": sync_replies(db, user.id)}
    except GmailError as exc: raise HTTPException(409, detail=str(exc)) from None
