"""Resume endpoints — upload + fetch, all scoped to the logged-in user."""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_resume_service
from app.db import models
from app.db.database import get_db
from app.services import ResumeService

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


def _svc(service: ResumeService, user: models.User) -> ResumeService:
    service.user = user
    return service


def _to_out(obj) -> dict:
    return {
        "id": obj.id,
        "filename": obj.filename,
        "content_type": obj.content_type,
        "parse_status": obj.parse_status,
        "parse_error": obj.parse_error,
        "profile": obj.profile,
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
    }


@router.post("", status_code=201)
async def upload_resume(file: UploadFile = File(...),
                        service: ResumeService = Depends(get_resume_service),
                        user: models.User = Depends(get_current_user)):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    try:
        obj = _svc(service, user).save_upload(
            data, file.filename or "resume", file.content_type or "application/octet-stream")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    out = _to_out(obj)
    out["raw_text"] = obj.raw_text
    return out


@router.get("")
def list_resumes(page: int | None = Query(default=None, ge=1),
                 page_size: int = Query(default=20, ge=1, le=100),
                 service: ResumeService = Depends(get_resume_service),
                 user: models.User = Depends(get_current_user)):
    svc = _svc(service, user)
    if page is None:
        return [_to_out(o) for o in svc.list()]
    items = svc.list(limit=page_size, offset=(page - 1) * page_size)
    return {"items": [_to_out(o) for o in items], "total": svc.count(),
            "page": page, "page_size": page_size}


@router.get("/{resume_id}")
def get_resume(resume_id: str, service: ResumeService = Depends(get_resume_service),
               user: models.User = Depends(get_current_user)):
    obj = _svc(service, user).get(resume_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="resume not found")
    out = _to_out(obj)
    out["raw_text"] = obj.raw_text
    return out


def _evidence_out(row: models.CandidateEvidence) -> dict:
    return {
        "id": row.id, "resume_id": row.resume_id, "ev_ref": row.ev_ref,
        "kind": row.kind, "assert_type": row.assert_type, "label": row.label,
        "fact": row.fact, "source_section": row.source_section,
        "line_start": row.line_start, "line_end": row.line_end,
        "source_text": row.source_text, "status": row.status,
        "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
    }


@router.get("/{resume_id}/evidence")
def list_evidence(resume_id: str, kind: str | None = None,
                  assert_type: str | None = None,
                  db: Session = Depends(get_db),
                  user: models.User = Depends(get_current_user)):
    """All candidate facts extracted from a resume, each with its source line
    span, so a user can see exactly what the system read and claims about."""
    svc_svc = ResumeService(db, user)
    if svc_svc.get(resume_id) is None:
        raise HTTPException(status_code=404, detail="resume not found")
    svc_svc.ensure_evidence(svc_svc.get(resume_id))
    q = db.query(models.CandidateEvidence).filter_by(user_id=user.id, resume_id=resume_id)
    if kind:
        q = q.filter_by(kind=kind)
    if assert_type:
        q = q.filter_by(assert_type=assert_type)
    return [_evidence_out(r) for r in q.order_by(models.CandidateEvidence.line_start).limit(500)]


@router.patch("/{resume_id}/evidence/{ev_id}")
def confirm_evidence(resume_id: str, ev_id: str, payload: dict,
                     db: Session = Depends(get_db),
                     user: models.User = Depends(get_current_user)):
    """Confirm or reject one extracted fact. Rejected facts are excluded from
    downstream tailoring evidence (status transitions extracted -> confirmed|rejected)."""
    status = (payload or {}).get("status")
    if status not in ("confirmed", "rejected", "extracted"):
        raise HTTPException(status_code=400,
                            detail="status must be one of confirmed|rejected|extracted")
    row = db.query(models.CandidateEvidence).filter_by(
        user_id=user.id, resume_id=resume_id, id=ev_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="evidence not found")
    from datetime import datetime as _dt

    row.status = status
    row.confirmed_at = _dt.now() if status in ("confirmed", "rejected") else None
    db.commit()
    db.refresh(row)
    return _evidence_out(row)
