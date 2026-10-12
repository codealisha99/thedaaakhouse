"""Integrations status — which providers exist and which are live."""

from fastapi import APIRouter, Depends

from app.ai.providers import provider_status
from app.api.dependencies import get_current_user
from app.db import models

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("")
def list_integrations(user: models.User = Depends(get_current_user)):
    _ = user
    return {"providers": provider_status()}
