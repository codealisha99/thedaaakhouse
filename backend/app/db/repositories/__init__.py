"""Repository layer — route handlers never touch the session directly."""

from sqlalchemy.orm import Session

from app.db import models


class ResumeRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> models.Resume:
        obj = models.Resume(**kwargs)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get(self, resume_id: str) -> models.Resume | None:
        return self.db.get(models.Resume, resume_id)

    def list(self, limit: int = 50) -> list[models.Resume]:
        return (
            self.db.query(models.Resume)
            .order_by(models.Resume.created_at.desc())
            .limit(limit)
            .all()
        )

    def update_profile(
        self, obj: models.Resume, profile: dict, status: str = "parsed", error: str | None = None
    ) -> models.Resume:
        obj.profile = profile
        obj.parse_status = status
        obj.parse_error = error
        self.db.commit()
        self.db.refresh(obj)
        return obj


class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> models.Job:
        obj = models.Job(**kwargs)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get(self, job_id: str) -> models.Job | None:
        return self.db.get(models.Job, job_id)

    def list(self, limit: int = 50) -> list[models.Job]:
        return self.db.query(models.Job).order_by(models.Job.created_at.desc()).limit(limit).all()

    def update_structured(self, obj: models.Job, structured: dict, status: str = "analyzed") -> models.Job:
        obj.structured = structured
        obj.status = status
        self.db.commit()
        self.db.refresh(obj)
        return obj
