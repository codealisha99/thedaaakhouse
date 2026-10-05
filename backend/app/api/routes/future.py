"""Placeholder routers — contracts for future milestones. Registered now so the
API surface matches the spec; each returns 501 until implemented."""

from fastapi import APIRouter

router = APIRouter(tags=["future"])


@router.get("/api/companies/{company_id}", status_code=501)
def get_company(company_id: str):
    return {"detail": "company research lands in milestone 3"}


@router.get("/api/interview/{job_id}", status_code=501)
def get_interview(job_id: str):
    return {"detail": "interview prep lands in milestone 4"}


@router.get("/api/projects/{job_id}", status_code=501)
def get_projects(job_id: str):
    return {"detail": "project recommendations land in milestone 4"}
