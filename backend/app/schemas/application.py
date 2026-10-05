"""Auth + application schemas."""

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class UserOut(BaseModel):
    id: str
    username: str


class ApplicationCreate(BaseModel):
    company: str = ""
    role: str = "Untitled role"
    location: str | None = None
    job_url: str | None = None
    date_saved: str | None = None
    date_applied: str | None = None
    status: str = "saved"
    salary: str | None = None
    interview_date: str | None = None
    next_step: str | None = None
    notes: str = ""
    raw_jd: str = ""
    job_id: str | None = None


class ApplicationUpdate(BaseModel):
    company: str | None = None
    role: str | None = None
    location: str | None = None
    job_url: str | None = None
    date_saved: str | None = None
    date_applied: str | None = None
    status: str | None = None
    salary: str | None = None
    interview_date: str | None = None
    next_step: str | None = None
    notes: str | None = None
    raw_jd: str | None = None
    resume_version_id: str | None = None


class ApplicationOut(BaseModel):
    id: str
    company: str
    role: str
    location: str | None = None
    job_url: str | None = None
    date_saved: str | None = None
    date_applied: str | None = None
    status: str
    salary: str | None = None
    ats_score: float | None = None
    resume_version_id: str | None = None
    interview_date: str | None = None
    next_step: str | None = None
    notes: str = ""
    jd_analysis: dict | None = None
    status_history: list = []
    created_at: str | None = None
    updated_at: str | None = None

    model_config = {"from_attributes": True}


class ResumeVersionOut(BaseModel):
    id: str
    resume_id: str | None = None
    application_id: str | None = None
    label: str
    missing_keywords: list = []
    ats_score: float | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


class TailorIn(BaseModel):
    resume_id: str
    label: str | None = None
