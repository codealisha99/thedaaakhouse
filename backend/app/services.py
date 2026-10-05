"""Service layer — business logic lives here, routes stay thin."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.analysis.ats import analyze_ats
from app.analysis.company import research_company
from app.analysis.interview import generate_prep
from app.analysis.keywords import analyze_jd
from app.analysis.tailor import tailor_resume
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import create_token, hash_password, verify_password
from app.db import models
from app.db.models import APPLICATION_STATUSES
from app.db.repositories import JobRepository, ResumeRepository
from app.ingestion.jd_parser import clean_text
from app.ingestion.resume_parser import get_resume_parser
from app.schemas.resume import CandidateProfile

log = get_logger(__name__)

ALLOWED_RESUME_EXTENSIONS = frozenset({".txt", ".pdf", ".doc", ".docx", ".tex"})
ALLOWED_RESUME_CONTENT_TYPES = frozenset({
    "text/plain",
    "text/latex",
    "application/x-latex",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",  # browsers send this for unknown types; extension still enforced
})


def _extract_text(data: bytes, content_type: str) -> str:
    """Decode text-based uploads. PDF/DOCX binary parsing: stored raw for now,
    UTF-8 best-effort (pypdf/python-docx extraction is planned)."""
    return data.decode("utf-8", errors="replace")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def register(self, username: str, password: str) -> models.User:
        username = username.strip()
        if not username:
            raise ValueError("username is required")
        if self.db.query(models.User).filter_by(username=username).first():
            raise ValueError("username is already taken")
        user = models.User(username=username, password_hash=hash_password(password))
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def login(self, username: str, password: str) -> tuple[models.User, str]:
        user = self.db.query(models.User).filter_by(username=username.strip()).first()
        if user is None or not verify_password(password, user.password_hash):
            log.warning("failed login attempt")  # never log passwords or tokens
            raise ValueError("invalid username or password")
        token = create_token(user.id, self.settings.jwt_secret, self.settings.jwt_expiry_min)
        return user, token


class ResumeService:
    def __init__(self, db: Session, user: models.User | None = None):
        self.db = db
        self.user = user
        self.repo = ResumeRepository(db)
        self.settings = get_settings()

    def _scope(self, query):
        if self.user is not None:
            query = query.filter(models.Resume.user_id == self.user.id)
        return query

    def save_upload(self, data: bytes, filename: str, content_type: str) -> models.Resume:
        if len(data) > self.settings.max_upload_bytes:
            raise ValueError(f"file exceeds {self.settings.max_upload_mb} MB limit")
        ext = "." + (filename.rsplit(".", 1)[-1].lower() if "." in filename else "")
        if ext not in ALLOWED_RESUME_EXTENSIONS:
            raise ValueError(
                f"unsupported file type '{ext or '(none)'}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_RESUME_EXTENSIONS))}"
            )
        if (content_type or "").split(";")[0].strip().lower() not in ALLOWED_RESUME_CONTENT_TYPES:
            raise ValueError(f"unsupported content type '{content_type}'")
        data_dir = Path(self.settings.data_dir) / "resumes"
        data_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._-")[:200] or "resume"
        dest = data_dir / safe_name
        i = 1
        while dest.exists():
            dest = data_dir / f"{dest.stem}_{i}{dest.suffix or '.bin'}"
            i += 1
        dest.write_bytes(data)

        raw_text = clean_text(_extract_text(data, content_type)).text
        profile: CandidateProfile = get_resume_parser().parse(raw_text, filename=safe_name)
        obj = self.repo.create(
            user_id=self.user.id if self.user else None,
            filename=safe_name,
            content_type=content_type,
            file_path=str(dest),
            raw_text=raw_text[:50_000],
            profile=profile.model_dump(),
            parse_status="parsed" if raw_text.strip() else "empty",
        )
        return obj

    def get(self, resume_id: str) -> models.Resume | None:
        obj = self.repo.get(resume_id)
        if obj is None:
            return None
        if self.user and obj.user_id not in (None, self.user.id):
            return None
        return obj

    def list(self, limit: int = 50) -> list[models.Resume]:
        q = self.db.query(models.Resume).order_by(models.Resume.created_at.desc())
        return self._scope(q).limit(limit).all()

    def list_versions(self, application_id: str | None = None) -> list[models.ResumeVersion]:
        q = self.db.query(models.ResumeVersion).order_by(models.ResumeVersion.created_at.desc())
        if self.user is not None:
            q = q.filter(models.ResumeVersion.user_id == self.user.id)
        if application_id:
            q = q.filter(models.ResumeVersion.application_id == application_id)
        return q.all()

    def get_version(self, version_id: str) -> models.ResumeVersion | None:
        obj = self.db.get(models.ResumeVersion, version_id)
        if obj is None:
            return None
        if self.user and obj.user_id != self.user.id:
            return None
        return obj


class JobService:
    def __init__(self, db: Session, user: models.User | None = None):
        self.db = db
        self.user = user
        self.repo = JobRepository(db)

    def create(self, title: str, company_name: str | None, source_url: str | None,
               location: str | None, raw_text: str) -> models.Job:
        cleaned = clean_text(raw_text).text
        if not cleaned.strip():
            raise ValueError("job description text is empty")
        return self.repo.create(
            user_id=self.user.id if self.user else None,
            title=title or "Untitled role",
            company_name=company_name,
            source_url=source_url,
            raw_text=cleaned[:50_000],
            location=location,
            status="created",
        )

    def get(self, job_id: str) -> models.Job | None:
        obj = self.repo.get(job_id)
        if obj is None:
            return None
        if self.user and obj.user_id not in (None, self.user.id):
            return None
        return obj

    def list(self, limit: int = 50) -> list[models.Job]:
        q = self.db.query(models.Job).order_by(models.Job.created_at.desc())
        if self.user is not None:
            q = q.filter(models.Job.user_id == self.user.id)
        return q.limit(limit).all()


class ApplicationService:
    """All tracker/application operations, always scoped to the owning user."""

    def __init__(self, db: Session, user: models.User):
        self.db = db
        self.user = user

    def _get_owned(self, model, obj_id: str):
        obj = self.db.get(model, obj_id)
        if obj is None or getattr(obj, "user_id", None) != self.user.id:
            return None
        return obj

    def create(self, **fields) -> models.Application:
        status = fields.get("status") or "saved"
        if status not in APPLICATION_STATUSES:
            raise ValueError(f"invalid status '{status}'. Choose from: {', '.join(APPLICATION_STATUSES)}")
        fields.setdefault("status_history", [{"to": status, "at": _now_iso()}])
        obj = models.Application(user_id=self.user.id, **fields)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        if obj.raw_jd and obj.raw_jd.strip() and not obj.jd_analysis:
            self.analyze_jd(obj)
        return obj

    def get(self, app_id: str) -> models.Application | None:
        return self._get_owned(models.Application, app_id)

    def list(self, status: str | None = None, search: str | None = None,
             sort: str = "updated", limit: int = 200) -> list[models.Application]:
        q = self.db.query(models.Application).filter(models.Application.user_id == self.user.id)
        if status:
            q = q.filter(models.Application.status == status)
        if search:
            like = f"%{search}%"
            q = q.filter(
                (models.Application.company.ilike(like))
                | (models.Application.role.ilike(like))
                | (models.Application.location.ilike(like))
            )
        order_col = {
            "updated": models.Application.updated_at.desc(),
            "created": models.Application.created_at.desc(),
            "company": models.Application.company.asc(),
            "status": models.Application.status.asc(),
        }.get(sort, models.Application.updated_at.desc())
        return q.order_by(order_col).limit(limit).all()

    def update(self, app_id: str, fields: dict) -> models.Application | None:
        obj = self.get(app_id)
        if obj is None:
            return None
        fields = {k: v for k, v in fields.items() if v is not None}
        if "status" in fields:
            if fields["status"] not in APPLICATION_STATUSES:
                raise ValueError(f"invalid status '{fields['status']}'")
            if fields["status"] != obj.status:
                hist = list(obj.status_history or [])
                hist.append({"from": obj.status, "to": fields["status"], "at": _now_iso()})
                obj.status_history = hist
        for k, v in fields.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        if "raw_jd" in fields and fields["raw_jd"]:
            self.analyze_jd(obj, commit=False)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, app_id: str) -> bool:
        obj = self.get(app_id)
        if obj is None:
            return False
        self.db.delete(obj)
        self.db.commit()
        return True

    # ---- connected operations ----

    def analyze_jd(self, obj: models.Application, commit: bool = True) -> dict:
        analysis = analyze_jd(obj.raw_jd)
        obj.jd_analysis = analysis
        if commit:
            self.db.commit()
            self.db.refresh(obj)
        return analysis

    def tailor(self, obj: models.Application, resume: models.Resume, label: str | None = None) -> models.ResumeVersion:
        if resume.user_id not in (None, self.user.id):
            raise ValueError("resume not found")
        if not obj.raw_jd.strip():
            raise ValueError("this application has no job description to tailor against")
        result = tailor_resume(resume.raw_text, obj.raw_jd)
        version = models.ResumeVersion(
            user_id=self.user.id,
            resume_id=resume.id,
            application_id=obj.id,
            label=label or f"{obj.company or 'Company'} — {obj.role} (v{self._next_version_no(obj.id)})",
            content=result["content"],
            changes=result["changes"],
            missing_keywords=result["missing_keywords"],
            ats_score=result["ats_before"],
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    def _next_version_no(self, app_id: str) -> int:
        return (
            self.db.query(models.ResumeVersion)
            .filter_by(application_id=app_id, user_id=self.user.id)
            .count()
            + 1
        )

    def attach_version(self, obj: models.Application, version: models.ResumeVersion) -> models.Application:
        if version.user_id != self.user.id:
            raise ValueError("resume version not found")
        obj.resume_version_id = version.id
        version.application_id = obj.id
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def run_ats(self, obj: models.Application, resume_text: str,
                version_id: str | None = None) -> models.ATSAnalysis:
        if not obj.raw_jd.strip():
            raise ValueError("this application has no job description to analyze against")
        breakdown = analyze_ats(resume_text, obj.raw_jd)
        row = models.ATSAnalysis(
            user_id=self.user.id,
            application_id=obj.id,
            resume_version_id=version_id,
            score=breakdown["score"],
            breakdown=breakdown,
        )
        self.db.add(row)
        obj.ats_score = breakdown["score"]
        self.db.commit()
        self.db.refresh(row)
        return row

    def run_interview_prep(self, obj: models.Application, resume_text: str = "") -> models.InterviewPrep:
        if not obj.raw_jd.strip():
            raise ValueError("this application has no job description — add one first")
        research = (
            self.db.query(models.Company)
            .filter_by(application_id=obj.id, user_id=self.user.id)
            .order_by(models.Company.created_at.desc())
            .first()
        )
        signals = (research.profile or {}).get("technology_signals", []) if research else []
        plan = generate_prep(obj.raw_jd, resume_text, obj.company or None, signals)
        row = models.InterviewPrep(user_id=self.user.id, application_id=obj.id, plan=plan)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def run_company_research(self, obj: models.Application, website: str | None = None) -> models.Company:
        result = research_company(obj.company or "Company", website)
        row = models.Company(
            user_id=self.user.id,
            application_id=obj.id,
            name=obj.company or "Company",
            website=result["website"],
            profile=result["profile"],
            sources=result["sources"],
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def latest(self, app_id: str) -> dict:
        """Full connected detail: analysis history, versions, prep, research."""
        obj = self.get(app_id)
        if obj is None:
            return {}
        ats = (
            self.db.query(models.ATSAnalysis)
            .filter_by(application_id=app_id, user_id=self.user.id)
            .order_by(models.ATSAnalysis.created_at.desc())
            .all()
        )
        preps = (
            self.db.query(models.InterviewPrep)
            .filter_by(application_id=app_id, user_id=self.user.id)
            .order_by(models.InterviewPrep.created_at.desc())
            .all()
        )
        research = (
            self.db.query(models.Company)
            .filter_by(application_id=app_id, user_id=self.user.id)
            .order_by(models.Company.created_at.desc())
            .all()
        )
        versions = (
            self.db.query(models.ResumeVersion)
            .filter_by(application_id=app_id, user_id=self.user.id)
            .order_by(models.ResumeVersion.created_at.desc())
            .all()
        )
        attached = self.db.get(models.ResumeVersion, obj.resume_version_id) if obj.resume_version_id else None
        return {
            "application": obj, "ats_history": ats, "interview_preps": preps,
            "research": research, "versions": versions, "attached_version": attached,
        }
