"""DB models. Relationships over duplication:

    User 1──* Application *──1 Job (JD store, optional)
    User 1──* Resume (master uploads) 1──* ResumeVersion (per-application tailoring)
    Application *──1 ResumeVersion (the version actually used)
    Application 1──* ATSAnalysis / InterviewPrep / CompanyResearch (history kept)
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base, TimestampMixin, uuid_key as _uuid
from app.outreach.delivery_models import EmailAccount, GmailOAuthState, OutreachDeliveryEvent, OutreachSend, OutreachSuppression  # noqa: F401

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

OPPORTUNITY_KINDS = ("vacancy", "startup_prospect")


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
    parsed_doc: Mapped[dict | None] = mapped_column(JSON, nullable=True)


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
    opportunity_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("opportunities.id"), nullable=True, unique=True, index=True
    )

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
    edited_manually: Mapped[bool] = mapped_column(default=False)
    # sha256[:16] of the master resume text at derivation time — proves the
    # version derives from a specific master snapshot.
    master_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)


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
    # True once the resume version this analysis was computed against was
    # manually edited afterwards: the numbers are no longer about that text.
    stale: Mapped[bool] = mapped_column(default=False)


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


class StudyPlan(Base, TimestampMixin):
    """Personalized study plan generated from a JD + the candidate's resume."""

    __tablename__ = "study_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    application_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("applications.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(512), default="Study plan")
    plan: Mapped[dict] = mapped_column(JSON, default=dict)


class TopicProgress(Base, TimestampMixin):
    """Per-topic mastery tracking inside a study plan."""

    __tablename__ = "topic_progress"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("study_plans.id"), index=True)
    topic: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), default="not_started")
    attempts: Mapped[int] = mapped_column(default=0)
    correct: Mapped[int] = mapped_column(default=0)


class InterviewSession(Base, TimestampMixin):
    """A mock/drill interview run: ordered questions, turns, running score."""

    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    application_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("applications.id"), nullable=True, index=True
    )
    mode: Mapped[str] = mapped_column(String(32), default="mock")
    difficulty: Mapped[str] = mapped_column(String(32), default="medium")
    status: Mapped[str] = mapped_column(String(32), default="active")
    questions: Mapped[list] = mapped_column(JSON, default=list)
    current_index: Mapped[int] = mapped_column(default=0)


class InterviewTurn(Base, TimestampMixin):
    """One answered question inside a session, with its evaluation."""

    __tablename__ = "interview_turns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("interview_sessions.id"), index=True)
    question: Mapped[dict] = mapped_column(JSON, default=dict)
    answer: Mapped[str] = mapped_column(Text, default="")
    evaluation: Mapped[dict] = mapped_column(JSON, default=dict)


class CareerProfile(Base, TimestampMixin):
    """One row per user. Demonstrated vs claimed vs to-learn skills stay distinct."""

    __tablename__ = "career_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True, index=True)
    education: Mapped[list] = mapped_column(JSON, default=list)
    skills_demonstrated: Mapped[list] = mapped_column(JSON, default=list)
    skills_claimed: Mapped[list] = mapped_column(JSON, default=list)
    skills_to_learn: Mapped[list] = mapped_column(JSON, default=list)
    experience: Mapped[list] = mapped_column(JSON, default=list)
    projects: Mapped[list] = mapped_column(JSON, default=list)
    target_roles: Mapped[list] = mapped_column(JSON, default=list)
    industries: Mapped[list] = mapped_column(JSON, default=list)
    domains: Mapped[list] = mapped_column(JSON, default=list)
    excluded_roles: Mapped[list] = mapped_column(JSON, default=list)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    goals: Mapped[list] = mapped_column(JSON, default=list)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)


class FitEvaluation(Base, TimestampMixin):
    """Stored career-fit verdict: config + provenance for reproducibility."""

    __tablename__ = "fit_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id"), index=True)
    classification: Mapped[str] = mapped_column(String(32), default="needs_review")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    factors: Mapped[dict] = mapped_column(JSON, default=dict)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    gaps: Mapped[list] = mapped_column(JSON, default=list)
    conflicts: Mapped[list] = mapped_column(JSON, default=list)
    unknown: Mapped[list] = mapped_column(JSON, default=list)
    recommendation: Mapped[str] = mapped_column(String(32), default="review")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    overridden: Mapped[bool] = mapped_column(default=False)


class OptimizationRun(Base, TimestampMixin):
    """One ATS optimize loop: initial score, attempts, final version + LaTeX."""

    __tablename__ = "optimization_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id"), index=True)
    resume_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("resumes.id"), nullable=True)
    policy: Mapped[dict] = mapped_column(JSON, default=dict)
    initial_score: Mapped[float] = mapped_column(Float, default=0.0)
    attempts: Mapped[list] = mapped_column(JSON, default=list)
    final_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("resume_versions.id"), nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="target_not_reached")
    stop_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_latex: Mapped[str | None] = mapped_column(Text, nullable=True)
    latex_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Which exact inputs produced the run — provenance for reproducibility.
    jd_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resume_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Reparse of the exported PDF vs the validated content (readability check).
    export_validation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    final_pdf_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # True once the run was based on a resume version that was later
    # manually edited: the run's outcome describes a superseded document.
    invalidated: Mapped[bool] = mapped_column(default=False)
    gaps: Mapped[list] = mapped_column(JSON, default=list)
    stage_trace: Mapped[list] = mapped_column(JSON, default=list)


class Organization(Base, TimestampMixin):
    """Canonical company identity established for a user's opportunities.

    Distinct from the research-snapshot `companies` table: this row carries the
    verified name/domain provenance for ranking and contact research. Never
    invented — an unestablished name stays null until sourced.
    """

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    domain: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)


class Opportunity(Base, TimestampMixin):
    """A ranked work opportunity: a vacancy backed by a listing, or a
    startup prospect with no vacancy (job_id and description stay null —
    never a synthetic JD)."""

    __tablename__ = "opportunities"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'startup_prospect') OR (job_id IS NOT NULL AND title IS NOT NULL)",
            name="ck_opportunity_vacancy_requires_listing",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), default="vacancy", index=True)
    job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    latest_evaluation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("opportunity_evaluations.id"), nullable=True
    )
    # Filterable projection of the latest evaluation (kept in sync by the
    # opportunity service; the versioned snapshot stays authoritative).
    eligibility_status: Mapped[str] = mapped_column(String(16), default="unknown")
    fit_classification: Mapped[str] = mapped_column(String(32), default="needs_review")
    fit_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    competition_status: Mapped[str] = mapped_column(String(16), default="unknown")
    competition_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    competition_comparable: Mapped[bool] = mapped_column(Boolean, default=False)
    competition_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    competition_platform: Mapped[str | None] = mapped_column(String(128), nullable=True)
    competition_meaning: Mapped[str | None] = mapped_column(String(128), nullable=True)
    potentially_overlooked: Mapped[bool] = mapped_column(Boolean, default=False)
    excluded: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    exclusion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OpportunityEvaluation(Base, TimestampMixin):
    """Versioned ranking snapshot: eligibility, fit, competition evidence and
    the priority formula inputs — kept separate, never conflated."""

    __tablename__ = "opportunity_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    opportunity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("opportunities.id"), nullable=False, index=True
    )
    evaluation_no: Mapped[int] = mapped_column(Integer, nullable=False)
    eligibility_status: Mapped[str] = mapped_column(String(16), default="unknown")
    eligibility_reasons: Mapped[list] = mapped_column(JSON, default=list)
    eligibility_checks: Mapped[list] = mapped_column(JSON, default=list)
    fit_classification: Mapped[str] = mapped_column(String(32), default="needs_review")
    fit_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fit_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fit_conflicts: Mapped[list] = mapped_column(JSON, default=list)
    fit_unknowns: Mapped[list] = mapped_column(JSON, default=list)
    competition: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    signals: Mapped[list] = mapped_column(JSON, default=list)
    priority_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    contributions: Mapped[list] = mapped_column(JSON, default=list)
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class ApplicantCountObservation(Base, TimestampMixin):
    """One measured applicant-count signal. Source, time and measurement
    meaning are recorded with the count: clicks are not applications, and
    unlike platforms are never compared as equal measurements."""

    __tablename__ = "applicant_count_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    opportunity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("opportunities.id"), nullable=False, index=True
    )
    observed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    platform: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    meaning: Mapped[str] = mapped_column(String(128), default="unknown")
    comparable: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class CandidateEvidence(Base, TimestampMixin):
    """One validated candidate fact with a stable source reference.

    Every row cites a resume line span (`source_text`, `line_start/end`) and
    an `ev_ref` id stable for that resume text. `assert_type` keeps
    demonstrated (found inside experience/projects bullets) apart from
    claimed (skills list only) and stated (verbatim facts). `status` carries
    the user's confirmation state: extracted -> confirmed|rejected. Rejected
    facts are excluded from downstream tailoring evidence.
    """

    __tablename__ = "candidate_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    resume_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("resumes.id"), nullable=True, index=True)
    ev_ref: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    assert_type: Mapped[str] = mapped_column(String(16), default="stated")
    label: Mapped[str] = mapped_column(String(512), default="")
    fact: Mapped[dict] = mapped_column(JSON, default=dict)
    source_section: Mapped[str] = mapped_column(String(64), default="")
    line_start: Mapped[int] = mapped_column(default=0)
    line_end: Mapped[int] = mapped_column(default=0)
    source_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="extracted")  # extracted|confirmed|rejected
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
