"""Applications — the tracker + connected workspace. All user-scoped."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import models
from app.db.database import get_db
from app.db.models import APPLICATION_STATUSES
from app.schemas.application import (
    ApplicationCreate,
    ApplicationOut,
    ApplicationUpdate,
    ResumeVersionOut,
    TailorIn,
)
from app.services import ApplicationService, ResumeService

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _svc(db: Session, user: models.User) -> ApplicationService:
    return ApplicationService(db, user)


def _out(obj: models.Application) -> dict:
    return {
        "id": obj.id, "company": obj.company, "role": obj.role, "location": obj.location,
        "job_url": obj.job_url, "date_saved": obj.date_saved, "date_applied": obj.date_applied,
        "status": obj.status, "salary": obj.salary, "ats_score": obj.ats_score,
        "resume_version_id": obj.resume_version_id, "interview_date": obj.interview_date,
        "next_step": obj.next_step, "notes": obj.notes, "jd_analysis": obj.jd_analysis,
        "raw_jd": obj.raw_jd,
        "status_history": obj.status_history or [],
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


def _version_out(v: models.ResumeVersion) -> dict:
    return {
        "id": v.id, "resume_id": v.resume_id, "application_id": v.application_id,
        "label": v.label, "missing_keywords": v.missing_keywords or [],
        "ats_score": v.ats_score,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


@router.get("/statuses")
def list_statuses():
    return {"statuses": list(APPLICATION_STATUSES)}


@router.post("", status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db),
                       user: models.User = Depends(get_current_user)):
    try:
        obj = _svc(db, user).create(**payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _out(obj)


@router.get("")
def list_applications(status: str | None = Query(default=None),
                      search: str | None = Query(default=None),
                      sort: str = Query(default="updated"),
                      page: int | None = Query(default=None, ge=1),
                      page_size: int = Query(default=20, ge=1, le=100),
                      db: Session = Depends(get_db),
                      user: models.User = Depends(get_current_user)):
    svc = _svc(db, user)
    if page is None:
        # Legacy shape (bare array) — default UI path, unchanged.
        return [_out(o) for o in svc.list(status=status, search=search, sort=sort)]
    items = svc.list(status=status, search=search, sort=sort,
                     limit=page_size, offset=(page - 1) * page_size)
    return {
        "items": [_out(o) for o in items],
        "total": svc.count(status=status, search=search),
        "page": page,
        "page_size": page_size,
    }


@router.get("/{app_id}")
def get_application(app_id: str, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    data = _svc(db, user).latest(app_id)
    if not data:
        raise HTTPException(status_code=404, detail="application not found")
    return {
        "application": _out(data["application"]),
        "attached_version": _version_out(data["attached_version"]) if data["attached_version"] else None,
        "versions": [_version_out(v) for v in data["versions"]],
        "ats_history": [
            {"id": a.id, "score": a.score, "breakdown": a.breakdown,
             "created_at": a.created_at.isoformat() if a.created_at else None}
            for a in data["ats_history"]
        ],
        "interview_preps": [
            {"id": p.id, "plan": p.plan,
             "created_at": p.created_at.isoformat() if p.created_at else None}
            for p in data["interview_preps"]
        ],
        "research": [
            {"id": r.id, "name": r.name, "website": r.website, "profile": r.profile,
             "sources": r.sources or []}
            for r in data["research"]
        ],
    }


@router.patch("/{app_id}")
def update_application(app_id: str, payload: ApplicationUpdate, db: Session = Depends(get_db),
                       user: models.User = Depends(get_current_user)):
    try:
        obj = _svc(db, user).update(app_id, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if obj is None:
        raise HTTPException(status_code=404, detail="application not found")
    return _out(obj)


@router.delete("/{app_id}", status_code=204)
def delete_application(app_id: str, db: Session = Depends(get_db),
                       user: models.User = Depends(get_current_user)):
    if not _svc(db, user).delete(app_id):
        raise HTTPException(status_code=404, detail="application not found")


@router.post("/{app_id}/analyze-jd")
def analyze_jd(app_id: str, db: Session = Depends(get_db),
               user: models.User = Depends(get_current_user)):
    svc = _svc(db, user)
    obj = svc.get(app_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="application not found")
    try:
        return svc.analyze_jd(obj)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{app_id}/tailor", status_code=201)
def tailor_resume(app_id: str, payload: TailorIn, db: Session = Depends(get_db),
                  user: models.User = Depends(get_current_user)):
    svc = _svc(db, user)
    obj = svc.get(app_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="application not found")
    resume = ResumeService(db, user).get(payload.resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="resume not found")
    try:
        version = svc.tailor(obj, resume, payload.label)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    svc.attach_version(obj, version)  # tailored version auto-attaches to its application
    return _version_out(version)


@router.post("/{app_id}/attach-version")
def attach_version(app_id: str, payload: dict, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    svc = _svc(db, user)
    obj = svc.get(app_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="application not found")
    version = ResumeService(db, user).get_version(payload.get("resume_version_id", ""))
    if version is None:
        raise HTTPException(status_code=404, detail="resume version not found")
    try:
        return _out(svc.attach_version(obj, version))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{app_id}/ats", status_code=201)
def run_ats(app_id: str, payload: dict, db: Session = Depends(get_db),
            user: models.User = Depends(get_current_user)):
    svc = _svc(db, user)
    obj = svc.get(app_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="application not found")
    rsvc = ResumeService(db, user)
    text, version_id = "", None
    if payload.get("resume_version_id"):
        v = rsvc.get_version(payload["resume_version_id"])
        if v is None:
            raise HTTPException(status_code=404, detail="resume version not found")
        text, version_id = v.content, v.id
    elif payload.get("resume_id"):
        r = rsvc.get(payload["resume_id"])
        if r is None:
            raise HTTPException(status_code=404, detail="resume not found")
        text = r.raw_text
    else:
        attached = db.get(models.ResumeVersion, obj.resume_version_id) if obj.resume_version_id else None
        if attached is None or attached.user_id != user.id:
            raise HTTPException(status_code=400, detail="no resume attached — attach a version or pass resume_id")
        text, version_id = attached.content, attached.id
    try:
        row = svc.run_ats(obj, text, version_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": row.id, "score": row.score, "breakdown": row.breakdown}


@router.post("/{app_id}/interview-prep", status_code=201)
def interview_prep(app_id: str, payload: dict, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    svc = _svc(db, user)
    obj = svc.get(app_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="application not found")
    resume_text = ""
    if payload.get("resume_id"):
        r = ResumeService(db, user).get(payload["resume_id"])
        resume_text = r.raw_text if r else ""
    try:
        row = svc.run_interview_prep(obj, resume_text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": row.id, "plan": row.plan}


@router.post("/{app_id}/company-research", status_code=201)
def company_research(app_id: str, payload: dict, db: Session = Depends(get_db),
                     user: models.User = Depends(get_current_user)):
    svc = _svc(db, user)
    obj = svc.get(app_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="application not found")
    try:
        row = svc.run_company_research(obj, (payload.get("website") or "").strip() or None)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"id": row.id, "name": row.name, "website": row.website,
            "profile": row.profile, "sources": row.sources or []}


@router.get("/versions/all")
def list_versions(application_id: str | None = None, db: Session = Depends(get_db),
                  user: models.User = Depends(get_current_user)):
    return [_version_out(v) for v in ResumeService(db, user).list_versions(application_id)]


@router.get("/versions/{version_id}")
def get_version(version_id: str, db: Session = Depends(get_db),
                user: models.User = Depends(get_current_user)):
    v = ResumeService(db, user).get_version(version_id)
    if v is None:
        raise HTTPException(status_code=404, detail="resume version not found")
    out = _version_out(v)
    out["content"] = v.content
    out["changes"] = v.changes or []
    return out
