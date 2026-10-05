"""Resume endpoints — upload + fetch, all scoped to the logged-in user."""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.api.dependencies import get_current_user, get_resume_service
from app.db import models
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
