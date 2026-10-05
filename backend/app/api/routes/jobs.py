"""Job endpoints — submit JD, fetch, and stub future AI workflow triggers.

Long-running AI routes return 501 with a clear message until their milestone
lands. This keeps the API contract visible without faking analysis.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_current_user, get_job_service
from app.db import models
from app.schemas.job import JobCreate
from app.services import JobService

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

NOT_READY = "not implemented in milestone 1 — see README status table"


def _to_out(obj, detail: bool = False) -> dict:
    base = {
        "id": obj.id,
        "title": obj.title,
        "company_name": obj.company_name,
        "source_url": obj.source_url,
        "location": obj.location,
        "status": obj.status,
        "structured": obj.structured,
    }
    if detail:
        base["raw_text"] = obj.raw_text
    return base


@router.post("", status_code=201)
def create_job(payload: JobCreate, service: JobService = Depends(get_job_service),
               user: models.User = Depends(get_current_user)):
    service.user = user
    try:
        obj = service.create(
            title=payload.title,
            company_name=payload.company_name,
            source_url=str(payload.source_url) if payload.source_url else None,
            location=payload.location,
            raw_text=payload.raw_text,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_out(obj)


@router.get("")
def list_jobs(page: int | None = Query(default=None, ge=1),
              page_size: int = Query(default=20, ge=1, le=100),
              service: JobService = Depends(get_job_service),
              user: models.User = Depends(get_current_user)):
    service.user = user
    if page is None:
        return [_to_out(o) for o in service.list()]
    items = service.list(limit=page_size, offset=(page - 1) * page_size)
    return {"items": [_to_out(o) for o in items], "total": service.count(),
            "page": page, "page_size": page_size}


@router.get("/{job_id}")
def get_job(job_id: str, service: JobService = Depends(get_job_service),
            user: models.User = Depends(get_current_user)):
    service.user = user
    obj = service.get(job_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _to_out(obj, detail=True)


for _op in ["analyze", "match", "tailor-resume", "company-research", "interview-prep", "project-recommendations"]:
    pass


@router.post("/{job_id}/analyze", status_code=501)
def analyze_job(job_id: str):
    return {"detail": f"analyze {NOT_READY}"}


@router.post("/{job_id}/match", status_code=501)
def match_job(job_id: str):
    return {"detail": f"match {NOT_READY}"}


@router.post("/{job_id}/tailor-resume", status_code=501)
def tailor_resume(job_id: str):
    return {"detail": f"tailor-resume {NOT_READY}"}


@router.post("/{job_id}/company-research", status_code=501)
def company_research(job_id: str):
    return {"detail": f"company-research {NOT_READY}"}


@router.post("/{job_id}/interview-prep", status_code=501)
def interview_prep(job_id: str):
    return {"detail": f"interview-prep {NOT_READY}"}


@router.post("/{job_id}/project-recommendations", status_code=501)
def project_recommendations(job_id: str):
    return {"detail": f"project-recommendations {NOT_READY}"}
