"""Auth routes — register, login, me."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.ratelimit import auth_limiter
from app.db import models
from app.db.database import get_db
from app.schemas.application import LoginIn, RegisterIn, TokenOut, UserOut
from app.services import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _check_rate_limit(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    if not auth_limiter.allow(f"auth:{client}"):
        raise HTTPException(status_code=429, detail="Too many attempts. Wait a minute and try again.")


@router.post("/register", response_model=TokenOut, status_code=201)
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)):
    _check_rate_limit(request)
    svc = AuthService(db)
    try:
        user = svc.register(payload.username, payload.password)
        _, token = svc.login(payload.username, payload.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TokenOut(access_token=token, username=user.username)


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    _check_rate_limit(request)
    try:
        user, token = AuthService(db).login(payload.username, payload.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return TokenOut(access_token=token, username=user.username)


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(get_current_user)):
    return UserOut(id=user.id, username=user.username)
