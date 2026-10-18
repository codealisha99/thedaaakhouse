"""Outreach draft endpoints. Drafting/previewing is local and never sends."""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import models
from app.db.database import get_db
from app.schemas.outreach import DraftCreateIn, DraftOut, DraftPatchIn, SuppressionIn
from app.outreach.service import DraftError, OutreachService
from app.outreach.delivery_models import EmailAccount, OutreachDeliveryEvent, OutreachSend, OutreachSuppression
from app.outreach.gmail import GmailError, add_suppression
from app.workflows.service import TaskService, TaskConflict

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


@router.post("/drafts/{draft_id}/send", status_code=202)
def send_draft(draft_id: str, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
               db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    if not idempotency_key:
        raise HTTPException(400, detail="Idempotency-Key header is required")
    draft = OutreachService(db, user.id).get(draft_id)
    if draft is None: raise HTTPException(404, detail={"code": "draft_not_found", "detail": "draft not found"})
    account = db.query(EmailAccount).filter_by(user_id=user.id, status="connected").first()
    if account is None: raise HTTPException(409, detail={"code": "gmail_disconnected", "detail": "connect Gmail first"})
    payload = {"draft_id": draft.id, "payload_sha256": draft.payload_sha256}
    if db.query(OutreachSuppression).filter_by(user_id=user.id, email=draft.recipient_email.lower()).first():
        raise HTTPException(409, detail={"code": "recipient_suppressed", "detail": "recipient is suppressed"})
    try:
        task, replayed = TaskService(db, user.id).enqueue("outreach.send", payload, idempotency_key=idempotency_key)
    except TaskConflict as exc:
        raise HTTPException(409, detail={"code": "idempotency_conflict", "existing_task_id": exc.existing_task_id}) from None
    return {"task_id": task.id, "status": task.status, "poll_url": f"/api/tasks/{task.id}", "replayed": replayed,
            "draft_id": draft.id, "payload_sha256": draft.payload_sha256}


@router.get("/sends")
def list_sends(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rows = db.query(OutreachSend).filter_by(user_id=user.id).order_by(OutreachSend.created_at.desc()).limit(100).all()
    return [{"id": r.id, "draft_id": r.draft_id, "status": r.status, "provider_message_id": r.provider_message_id,
             "payload_sha256": r.payload_sha256, "created_at": r.created_at, "events": [
                 {"kind": e.kind, "occurred_at": e.occurred_at} for e in db.query(OutreachDeliveryEvent).filter_by(send_id=r.id).order_by(OutreachDeliveryEvent.occurred_at).all()]}
            for r in rows]


@router.get("/sends/{send_id}")
def get_send(send_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    row = db.query(OutreachSend).filter_by(id=send_id, user_id=user.id).first()
    if row is None: raise HTTPException(404, detail="send not found")
    return {"id": row.id, "draft_id": row.draft_id, "status": row.status,
            "provider_message_id": row.provider_message_id, "thread_id": row.thread_id,
            "payload_sha256": row.payload_sha256, "payload_snapshot": row.payload_snapshot,
            "events": [{"kind": e.kind, "occurred_at": e.occurred_at, "detail": e.detail}
                       for e in db.query(OutreachDeliveryEvent).filter_by(send_id=row.id).order_by(OutreachDeliveryEvent.occurred_at).all()]}


@router.post("/suppressions", status_code=201)
def suppress_recipient(payload: SuppressionIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    email = payload.email.strip().lower()
    reason = payload.reason
    if "@" not in email or len(email) > 320: raise HTTPException(422, detail="valid email required")
    try: add_suppression(db, user.id, email, reason)
    except GmailError as exc: raise HTTPException(422, detail=str(exc)) from None
    return {"suppressed": True, "email": email, "reason": reason}
