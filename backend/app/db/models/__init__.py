"""DB models. Relationships over duplication:

    User 1──* Application *──1 Job (JD store, optional)
    User 1──* Resume (master uploads) 1──* ResumeVersion (per-application tailoring)
    Application *──1 ResumeVersion (the version actually used)
    Application 1──* ATSAnalysis / InterviewPrep / CompanyResearch (history kept)
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

APPLICATION_STATUSES = (
    "saved",
    "applied",
    "oa",
    "interview",
    "final_round",
    "offer",
    "rejected",
    "withdrawn",
)


def _uuid() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))


class Resume(Base, TimestampMixin):
    """Master resume upload: raw file + parsed structured profile."""

    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    file_path: Mapped[str] = mapped_column(String(1024))
    raw_text: Mapped[str] = mapped_column(Text, default="")
    profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parse_status: Mapped[str] = mapped_column(String(32), default="pending")
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Job(Base, TimestampMixin):
    """A job description: raw text/URL + structured extraction."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(512), default="Untitled role")
    company_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str | None] = mapped_column(String(512), nullable=True)
    structured: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="created")


class Application(Base, TimestampMixin):
    """One job application — the connected object everything attaches to."""

    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=True)

    company: Mapped[str] = mapped_column(String(512), default="")
    role: Mapped[str] = mapped_column(String(512), default="Untitled role")
    location: Mapped[str | None] = mapped_column(String(512), nullable=True)
    job_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_saved: Mapped[str | None] = mapped_column(String(32), nullable=True)  # ISO date
    date_applied: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="saved", index=True)
    salary: Mapped[str | None] = mapped_column(String(256), nullable=True)
    ats_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    resume_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("resume_versions.id"), nullable=True
    )
    interview_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    next_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    raw_jd: Mapped[str] = mapped_column(Text, default="")
    jd_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status_history: Mapped[list] = mapped_column(JSON, default=list)


class ResumeVersion(Base, TimestampMixin):
    """A tailored resume derived from a master Resume, optionally for an Application."""

    __tablename__ = "resume_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    resume_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("resumes.id"), nullable=True
    )
    application_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("applications.id"), nullable=True, index=True
    )
    label: Mapped[str] = mapped_column(String(512), default="Tailored resume")
    content: Mapped[str] = mapped_column(Text, default="")
    changes: Mapped[list] = mapped_column(JSON, default=list)
    missing_keywords: Mapped[list] = mapped_column(JSON, default=list)
    ats_score: Mapped[float | None] = mapped_column(Float, nullable=True)


class ATSAnalysis(Base, TimestampMixin):
    __tablename__ = "ats_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    application_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("applications.id"), nullable=True, index=True
    )
    resume_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("resume_versions.id"), nullable=True
    )
    score: Mapped[float] = mapped_column(Float, default=0.0)
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)


class InterviewPrep(Base, TimestampMixin):
    __tablename__ = "interview_preps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    application_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("applications.id"), nullable=True, index=True
    )
    plan: Mapped[dict] = mapped_column(JSON, default=dict)


class Company(Base, TimestampMixin):
    """Researched company profile. Every external claim must carry source metadata."""

    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    application_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("applications.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(512))
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
