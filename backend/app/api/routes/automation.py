"""Automation API — bounded owner-scoped policy + approval management.

Policies are standing authorizations with quota; approvals bind exactly one
payload hash for one action kind, expire, and are invalidated by edits of the
recipient/body/artifact (later steps pass fresh payload hashes after edits).
All routes stay strictly owner-scoped.
"""

from datetime import datetime

from app.api.dependencies import get_current_user
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db
from app.schemas.automation import (
    ApprovalCreate,
    ApprovalOut,
    PolicyCreate,
    PolicyOut,
    PolicyUpdate,
    PolicyUsageOut,
)
from app.core.logging import get_logger
from app.workflows.automation import (
    approval_out,
    AutomationError,
    AutomationService,
    policy_out,
)

log = get_logger(__name__)

router = APIRouter(prefix="/api/automation", tags=["automation"])


def _svc(db: Session, user: models.User) -> AutomationService:
    return AutomationService(db, user.id)


def _die(err: AutomationError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(err))


# --------------------------------------------------------------------------- #
# Policies

@router.post("/policies", status_code=201)
def create_policy(
    payload: PolicyCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> PolicyOut:
    expires_at = None
    if payload.expires_at:
        try:
            expires_at = datetime.fromisoformat(payload.expires_at.replace("Z", "+00:00"))
        except ValueError:
            raise _die(AutomationError("expires_at must be an ISO timestamp")) from None
    try:
        policy = _svc(db, user).create_policy(
            name=payload.name,
            allowed_actions=payload.allowed_actions,
            constraints=payload.constraints,
            ttl_seconds=payload.ttl_seconds,
            expires_at=expires_at,
        )
    except AutomationError as err:
        raise _die(err) from None
    return PolicyOut(**policy_out(policy))


@router.get("/policies")
def list_policies(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[PolicyOut]:
    return [PolicyOut(**policy_out(p)) for p in _svc(db, user).list_policies()]


@router.get("/policies/{policy_id}")
def get_policy(
    policy_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> PolicyOut:
    policy = _svc(db, user).get_policy(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="policy not found")
    return PolicyOut(**policy_out(policy))


@router.get("/policies/{policy_id}/usage")
def policy_usage(
    policy_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> PolicyUsageOut:
    try:
        return PolicyUsageOut(**_svc(db, user).usage(policy_id))
    except LookupError:
        raise HTTPException(status_code=404, detail="policy not found") from None


@router.patch("/policies/{policy_id}")
def update_policy(
    policy_id: str,
    payload: PolicyUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> PolicyOut:
    svc = _svc(db, user)
    if payload.revoke:
        policy = svc.revoke_policy(policy_id)
        if policy is None:
            raise HTTPException(status_code=404, detail="policy not found")
        return PolicyOut(**policy_out(policy))
    try:
        policy = svc.update_policy_limit(policy_id, payload.daily_limit)
    except LookupError:
        raise HTTPException(status_code=404, detail="policy not found") from None
    except AutomationError as err:
        raise _die(err) from None
    return PolicyOut(**policy_out(policy))


@router.post("/policies/{policy_id}/revoke")
def revoke_policy(
    policy_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> PolicyOut:
    policy = _svc(db, user).revoke_policy(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="policy not found")
    return PolicyOut(**policy_out(policy))


# --------------------------------------------------------------------------- #
# Approvals

@router.post("/approvals", status_code=201)
def create_approval(
    payload: ApprovalCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> ApprovalOut:
    try:
        approval = _svc(db, user).create_approval(
            action_kind=payload.action_kind,
            payload=payload.payload,
            ttl_seconds=payload.ttl_seconds,
            object_ref=payload.object_ref,
            artifact_hash=payload.artifact_hash,
        )
    except AutomationError as err:
        raise _die(err) from None
    return ApprovalOut(**approval_out(approval))


@router.get("/approvals")
def list_approvals(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[ApprovalOut]:
    return [ApprovalOut(**approval_out(a)) for a in _svc(db, user).list_approvals()]


@router.post("/approvals/{approval_id}/revoke")
def revoke_approval(
    approval_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> ApprovalOut:
    approval = _svc(db, user).revoke_approval(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="approval not found")
    return ApprovalOut(**approval_out(approval))
