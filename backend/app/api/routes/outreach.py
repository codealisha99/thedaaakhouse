"""Outreach draft endpoints. Drafting/previewing is local and never sends."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import models
from app.db.database import get_db
from app.schemas.outreach import DraftCreateIn, DraftOut, DraftPatchIn
from app.outreach.service import DraftError, OutreachService

router = APIRouter(prefix="/api/outreach", tags=["outreach"])


def _out(row, approval_invalidated: bool = False) -> dict:
    return DraftOut(
        id=row.id, opportunity_id=row.opportunity_id, mode=row.mode,
        recipient_email=row.recipient_email, recipient_name=row.recipient_name,
        recipient_role=row.recipient_role, recipient_identity=row.recipient_identity,
        contact_source_url=row.contact_source_url, contact_source_kind=row.contact_source_kind,
        subject=row.subject, body=row.body, personalization=row.personalization or {},
        factuality_findings=row.factuality_findings or [], resume_version_id=row.resume_version_id,
        attachment_name=row.attachment_name, attachment_preview=row.attachment_text,
        attachment_sha256=row.attachment_sha256,
        payload_sha256=row.payload_sha256, revision=row.revision, status=row.status,
        approval_invalidated=approval_invalidated,
    ).model_dump()


def _error(err: DraftError) -> HTTPException:
    status = 404 if err.code in ("opportunity_not_found", "draft_not_found", "resume_not_found") else 422
    return HTTPException(status_code=status, detail={"code": err.code, "detail": err.detail})


@router.post("/drafts", status_code=201)
def create_draft(payload: DraftCreateIn, db: Session = Depends(get_db),
                 user: models.User = Depends(get_current_user)):
    try:
        row = OutreachService(db, user.id).create(**payload.model_dump())
    except DraftError as err:
        raise _error(err) from None
    return _out(row)


@router.get("/drafts")
def list_drafts(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return [_out(row) for row in OutreachService(db, user.id).list_for_user()]


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: str, db: Session = Depends(get_db),
              user: models.User = Depends(get_current_user)):
    row = OutreachService(db, user.id).get(draft_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "draft_not_found", "detail": "draft not found"})
    return _out(row)


@router.post("/drafts/{draft_id}/preview")
def preview_draft(draft_id: str, db: Session = Depends(get_db),
                  user: models.User = Depends(get_current_user)):
    """Return exactly the reviewed recipient/body/attachment metadata; no send."""
    return get_draft(draft_id, db, user)


@router.patch("/drafts/{draft_id}")
def edit_draft(draft_id: str, payload: DraftPatchIn, db: Session = Depends(get_db),
               user: models.User = Depends(get_current_user)):
    svc = OutreachService(db, user.id)
    row = svc.get(draft_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "draft_not_found", "detail": "draft not found"})
    try:
        row, invalidated = svc.edit(row, payload.model_dump(exclude_unset=True))
    except DraftError as err:
        raise _error(err) from None
    return _out(row, approval_invalidated=invalidated)
