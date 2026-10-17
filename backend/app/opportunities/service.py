"""Opportunity service: creation, evaluation, listing, saving.

Ownership: every row is user-owned; other-owner reads return None (404 at the
route). Saving an opportunity is idempotent — one opportunity maps to at most
one tracked application (enforced by a unique index on
applications.opportunity_id plus a pre-check, so concurrent saves still create
one application).
"""

import base64
import json
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import models
from app.opportunities.ranking import (
    COMPARABLE_MEANINGS,
    RankingWeights,
    evaluate_opportunity,
)
from app.services import _profile_out


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _domain_of(url: str | None) -> str | None:
    try:
        host = (urlparse(url or "").hostname or "").lower()
    except Exception:
        return None
    return host or None


def _evidence_url(entry: dict) -> str:
    return str(entry.get("source_url") or entry.get("url") or "")


class OpportunityService:
    def __init__(self, db: Session, user: models.User):
        self.db = db
        self.user = user

    # ---- ownership ----

    def _owned(self, obj, obj_id: str):
        row = self.db.get(obj, obj_id)
        if row is None or row.user_id != self.user.id:
            return None
        return row

    def _profile_dict(self) -> dict:
        p = self.db.query(models.CareerProfile).filter_by(user_id=self.user.id).first()
        return _profile_out(p) if p else {}

    # ---- creation ----

    def _get_or_create_org(self, name: str | None, domain: str | None,
                           website: str | None) -> models.Organization:
        q = self.db.query(models.Organization).filter_by(user_id=self.user.id)
        org = None
        if domain:
            org = q.filter(func.lower(models.Organization.domain) == domain.lower()).first()
        if org is None and name:
            org = q.filter(func.lower(models.Organization.name) == name.lower()).first()
        if org is None:
            org = models.Organization(user_id=self.user.id, name=name, domain=domain, website=website)
            self.db.add(org)
            self.db.commit()
            self.db.refresh(org)
        return org

    def create_vacancy(self, job_id: str) -> models.Opportunity:
        job = self.db.get(models.Job, job_id)
        # Legacy null-owner jobs stay importable (step-01 quarantine still pending);
        # other-owner jobs never are.
        if job is None or job.user_id not in (None, self.user.id):
            raise LookupError("job not found")
        domain = _domain_of(job.source_url)
        org = self._get_or_create_org(job.company_name, domain, job.source_url)
        opp = models.Opportunity(
            user_id=self.user.id, organization_id=org.id, kind="vacancy",
            job_id=job.id, title=job.title or "Untitled role",
            description=job.raw_text or None,
            source_evidence=[{"source_url": job.source_url, "kind": "job_listing",
                              "recorded_at": _now_iso()}] if job.source_url else [],
            first_seen_at=_now(),
        )
        self.db.add(opp)
        self.db.commit()
        self.db.refresh(opp)
        self.evaluate(opp.id)
        return self._owned(models.Opportunity, opp.id)

    def create_prospect(self, url: str, name: str | None = None,
                        note: str | None = None) -> models.Opportunity:
        """Startup prospect from a user-supplied URL. No vacancy, no synthetic
        JD: title/description stay null and the URL is recorded as the only
        source evidence."""
        url = (url or "").strip()
        try:
            parts = urlparse(url)
        except Exception as e:
            raise ValueError(f"invalid URL: {e}") from e
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("URL must be a valid http(s) address")
        domain = _domain_of(url)
        org = self._get_or_create_org(name, domain, url)
        opp = models.Opportunity(
            user_id=self.user.id, organization_id=org.id, kind="startup_prospect",
            job_id=None, title=None, description=None,
            source_evidence=[{"source_url": url, "method": "user_supplied",
                              "recorded_at": _now_iso(), "note": note}],
            first_seen_at=_now(),
        )
        self.db.add(opp)
        self.db.commit()
        self.db.refresh(opp)
        self.evaluate(opp.id)
        return self._owned(models.Opportunity, opp.id)

    # ---- evaluation ----

    def _opp_dict(self, opp: models.Opportunity) -> dict:
        org = self.db.get(models.Organization, opp.organization_id)
        return {
            "id": opp.id, "kind": opp.kind, "job_id": opp.job_id,
            "title": opp.title, "description": opp.description,
            "first_seen_at": opp.first_seen_at,
            "organization": {"name": org.name if org else None,
                             "domain": org.domain if org else None,
                             "location": org.location if org else None},
            "source_evidence": opp.source_evidence or [],
        }

    def _observations(self, opp_id: str) -> list[dict]:
        rows = (self.db.query(models.ApplicantCountObservation)
                .filter_by(opportunity_id=opp_id)
                .order_by(models.ApplicantCountObservation.observed_at.desc()).all())
        return [{"observed_count": r.observed_count, "platform": r.platform,
                 "source": r.source, "observed_at": r.observed_at, "meaning": r.meaning,
                 "comparable": bool(r.comparable), "note": r.note} for r in rows]

    def _evaluate_row(self, opp: models.Opportunity,
                      weights: RankingWeights | None = None) -> models.OpportunityEvaluation:
        job = self.db.get(models.Job, opp.job_id) if opp.job_id else None
        snapshot = evaluate_opportunity(
            self._opp_dict(opp),
            {"company_name": job.company_name, "location": job.location,
             "raw_text": job.raw_text} if job else None,
            self._profile_dict(),
            self._observations(opp.id),
            weights,
        )
        evaluation_no = (self.db.query(func.count(models.OpportunityEvaluation.id))
                         .filter_by(opportunity_id=opp.id).scalar() or 0) + 1
        row = models.OpportunityEvaluation(
            user_id=self.user.id, opportunity_id=opp.id, evaluation_no=evaluation_no,
            eligibility_status=snapshot["eligibility_status"],
            eligibility_reasons=snapshot["eligibility_reasons"],
            eligibility_checks=snapshot["eligibility_checks"],
            fit_classification=snapshot["fit_classification"],
            fit_score=snapshot["fit_score"],
            fit_factors=snapshot["fit_factors"],
            fit_conflicts=snapshot["fit_conflicts"],
            fit_unknowns=snapshot["fit_unknowns"],
            competition=snapshot["competition"],
            signals=snapshot["signals"],
            priority_score=snapshot["priority_score"],
            contributions=snapshot["contributions"],
            coverage=snapshot["coverage"],
            config=snapshot["config"],
        )
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError:
            # Concurrent evaluation: retry with the next version number.
            self.db.rollback()
            evaluation_no = (self.db.query(func.count(models.OpportunityEvaluation.id))
                             .filter_by(opportunity_id=opp.id).scalar() or 0) + 1
            row = models.OpportunityEvaluation(
                user_id=self.user.id, opportunity_id=opp.id, evaluation_no=evaluation_no,
                eligibility_status=snapshot["eligibility_status"],
                eligibility_reasons=snapshot["eligibility_reasons"],
                eligibility_checks=snapshot["eligibility_checks"],
                fit_classification=snapshot["fit_classification"],
                fit_score=snapshot["fit_score"],
                fit_factors=snapshot["fit_factors"],
                fit_conflicts=snapshot["fit_conflicts"],
                fit_unknowns=snapshot["fit_unknowns"],
                competition=snapshot["competition"],
                signals=snapshot["signals"],
                priority_score=snapshot["priority_score"],
                contributions=snapshot["contributions"],
                coverage=snapshot["coverage"],
                config=snapshot["config"],
            )
            self.db.add(row)
            self.db.commit()
        self.db.refresh(row)
        proj = snapshot["projection"]
        for k, v in proj.items():
            setattr(opp, k, v)
        opp.latest_evaluation_id = row.id
        self.db.commit()
        return row

    def evaluate(self, opportunity_id: str, weights: dict | None = None) -> dict:
        opp = self._owned(models.Opportunity, opportunity_id)
        if opp is None:
            raise LookupError("opportunity not found")
        cfg = RankingWeights(**weights) if weights else None
        if weights:
            cfg.validate()
        row = self._evaluate_row(opp, cfg)
        return self._eval_out(row)

    def _eval_out(self, row: models.OpportunityEvaluation) -> dict:
        return {
            "id": row.id, "opportunity_id": row.opportunity_id,
            "evaluation_no": row.evaluation_no,
            "eligibility": {"status": row.eligibility_status,
                            "reasons": row.eligibility_reasons or [],
                            "checks": row.eligibility_checks or []},
            "fit": {"classification": row.fit_classification, "score": row.fit_score,
                    "factors": row.fit_factors or {}, "conflicts": row.fit_conflicts or [],
                    "unknowns": row.fit_unknowns or []},
            "competition": row.competition or {"status": "missing"},
            "signals": row.signals or [],
            "priority": {"score": row.priority_score,
                         "contributions": row.contributions or [],
                         "coverage": row.coverage or {}},
            "config": row.config or {},
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    # ---- exclusion ----

    def exclude(self, opportunity_id: str, excluded: bool,
                reason: str | None = None) -> dict:
        opp = self._owned(models.Opportunity, opportunity_id)
        if opp is None:
            raise LookupError("opportunity not found")
        opp.excluded = bool(excluded)
        opp.exclusion_reason = reason or ""
        self.db.commit()
        self.db.refresh(opp)
        return self._item_out(opp)

    # ---- competition evidence ----

    def record_applicant_count(self, opportunity_id: str, count: int,
                               platform: str | None = None, source: str | None = None,
                               observed_at: datetime | None = None,
                               meaning: str = "unknown",
                               note: str | None = None) -> dict:
        """Record one measured observation, then re-evaluate so the versioned
        snapshot stays current. Counts from unlike measurements (clicks,
        views) are stored with comparable=false."""
        opp = self._owned(models.Opportunity, opportunity_id)
        if opp is None:
            raise LookupError("opportunity not found")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("observed_count must be a non-negative integer")
        meaning = (meaning or "unknown").strip().lower() or "unknown"
        comparable = meaning in COMPARABLE_MEANINGS
        row = models.ApplicantCountObservation(
            user_id=self.user.id, opportunity_id=opp.id, observed_count=count,
            platform=platform, source=source,
            observed_at=observed_at or _now(), meaning=meaning,
            comparable=comparable, note=note,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        self.evaluate(opp.id)
        return {
            "observation": {
                "id": row.id, "opportunity_id": row.opportunity_id,
                "observed_count": row.observed_count, "platform": row.platform,
                "source": row.source,
                "observed_at": row.observed_at.isoformat() if row.observed_at else None,
                "meaning": row.meaning, "comparable": bool(row.comparable),
                "note": row.note,
            },
            "evaluation": self._eval_out(
                self.db.get(models.OpportunityEvaluation, opp.latest_evaluation_id)),
        }

    # ---- list + detail ----

    def _item_out(self, opp: models.Opportunity) -> dict:
        org = self.db.get(models.Organization, opp.organization_id)
        return {
            "id": opp.id,
            "kind": opp.kind,
            "has_listing": opp.kind == "vacancy",
            "title": opp.title,
            "company": org.name if org else None,
            "domain": org.domain if org else None,
            "location": org.location if org else None,
            "eligibility": {"status": opp.eligibility_status},
            "fit": {"classification": opp.fit_classification, "score": opp.fit_score},
            "competition": {
                "status": opp.competition_status,
                "observed_count": opp.competition_count,
                "comparable": bool(opp.competition_comparable),
                "observed_at": (opp.competition_observed_at.isoformat()
                                if opp.competition_observed_at else None),
                "platform": opp.competition_platform,
                "meaning": opp.competition_meaning,
            },
            "potentially_overlooked": bool(opp.potentially_overlooked),
            "priority_score": opp.priority_score,
            "excluded": bool(opp.excluded),
            "exclusion_reason": opp.exclusion_reason,
            "created_at": opp.created_at.isoformat() if opp.created_at else None,
        }

    @staticmethod
    def _encode_cursor(opp: models.Opportunity) -> str:
        payload = {"p": opp.priority_score, "c": opp.created_at.isoformat(), "i": opp.id}
        return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()

    @staticmethod
    def _decode_cursor(cursor: str) -> dict:
        """Cursor carries (priority, created_at, id). `created_at` is quantized
        to the second and compared as a string: SQLite stores datetimes as
        fixed-format text, so naive datetime binding breaks tie comparisons."""
        try:
            payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
            p = payload.get("p")
            c = datetime.fromisoformat(payload["c"]).replace(microsecond=0)
            return {"p": float(p) if p is not None else None,
                    "c": c.isoformat(sep=" "), "i": payload["i"]}
        except Exception as e:
            raise ValueError("invalid cursor") from e

    def list(self, *, kind: str | None = None, eligibility: str | None = None,
             fit: str | None = None, competition: str | None = None,
             max_applicants: int | None = None, max_age_days: int = 30,
             overlooked: bool | None = None, min_priority: float | None = None,
             include_excluded: bool = False, cursor: str | None = None,
             limit: int = 20) -> dict:
        q = self.db.query(models.Opportunity).filter(models.Opportunity.user_id == self.user.id)
        if kind:
            if kind not in ("vacancy", "startup_prospect"):
                raise ValueError("kind must be 'vacancy' or 'startup_prospect'")
            q = q.filter(models.Opportunity.kind == kind)
        if eligibility:
            q = q.filter(models.Opportunity.eligibility_status == eligibility)
        if fit:
            q = q.filter(models.Opportunity.fit_classification == fit)
        if competition == "observed":
            q = q.filter(models.Opportunity.competition_status == "observed")
        elif competition == "missing":
            q = q.filter(models.Opportunity.competition_status == "missing")
        elif competition == "lower_observed":
            q = q.filter(
                models.Opportunity.competition_status == "observed",
                models.Opportunity.competition_comparable.is_(True),
                models.Opportunity.competition_count <= (max_applicants or 10_000),
                models.Opportunity.competition_observed_at >= _now() - timedelta(days=max_age_days),
            )
        if overlooked is not None:
            q = q.filter(models.Opportunity.potentially_overlooked.is_(overlooked))
        if min_priority is not None:
            q = q.filter(models.Opportunity.priority_score >= min_priority)
        if not include_excluded:
            q = q.filter(models.Opportunity.excluded.is_(False))

        total = q.count()

        # Deterministic keyset: priority (nulls last), created_at, id.
        if cursor:
            cur = self._decode_cursor(cursor)
            p, c, i = cur["p"], cur["c"], cur["i"]
            newer = (models.Opportunity.created_at < c) | (
                (models.Opportunity.created_at == c) & (models.Opportunity.id < i))
            if p is not None:
                cond = (models.Opportunity.priority_score < p) | (
                    (models.Opportunity.priority_score == p) & newer)
                cond = cond | models.Opportunity.priority_score.is_(None)
            else:
                cond = models.Opportunity.priority_score.is_(None) & newer
            q = q.filter(cond)
        q = q.order_by(models.Opportunity.priority_score.is_(None),
                       models.Opportunity.priority_score.desc(),
                       models.Opportunity.created_at.desc(),
                       models.Opportunity.id.desc())
        rows = q.limit(limit + 1).all()
        has_more = len(rows) > limit
        items = rows[:limit]
        return {
            "items": [self._item_out(o) for o in items],
            "total": total,
            "next_cursor": self._encode_cursor(items[-1]) if has_more and items else None,
        }

    def get(self, opportunity_id: str) -> dict:
        opp = self._owned(models.Opportunity, opportunity_id)
        if opp is None:
            raise LookupError("opportunity not found")
        org = self.db.get(models.Organization, opp.organization_id)
        job = self.db.get(models.Job, opp.job_id) if opp.job_id else None
        ev = (self.db.get(models.OpportunityEvaluation, opp.latest_evaluation_id)
              if opp.latest_evaluation_id else None)
        obs = (self.db.query(models.ApplicantCountObservation)
               .filter_by(opportunity_id=opp.id)
               .order_by(models.ApplicantCountObservation.observed_at.desc()).all())
        app = (self.db.query(models.Application)
               .filter_by(user_id=self.user.id, opportunity_id=opp.id).first())
        out = self._item_out(opp)
        out.update({
            "description": opp.description,  # null for prospects — never a synthetic JD
            "organization": {
                "id": org.id, "name": org.name, "domain": org.domain,
                "website": org.website, "location": org.location,
                "sources": org.sources or [],
            } if org else None,
            "job": {"id": job.id, "title": job.title} if job else None,
            "first_seen_at": opp.first_seen_at.isoformat() if opp.first_seen_at else None,
            "source_evidence": opp.source_evidence or [],
            "evaluations": None,
            "observations": [{
                "id": o.id, "observed_count": o.observed_count, "platform": o.platform,
                "source": o.source,
                "observed_at": o.observed_at.isoformat() if o.observed_at else None,
                "meaning": o.meaning, "comparable": bool(o.comparable), "note": o.note,
            } for o in obs],
            "application": {"id": app.id, "status": app.status} if app else None,
        })
        if ev:
            out["evaluation"] = self._eval_out(ev)
            out["competition"] = ev.competition or {"status": "missing"}
        else:
            out["evaluation"] = None
        return out

    # ---- save (idempotent) ----

    def save(self, opportunity_id: str) -> tuple[dict, bool]:
        """Link the opportunity to a tracked application. Saving twice returns
        the same application — one opportunity maps to at most one
        application (unique index backs the pre-check)."""
        opp = self._owned(models.Opportunity, opportunity_id)
        if opp is None:
            raise LookupError("opportunity not found")
        if opp.excluded:
            raise ValueError("opportunity is excluded — unexclude it before saving")
        org = self.db.get(models.Organization, opp.organization_id)
        job = self.db.get(models.Job, opp.job_id) if opp.job_id else None

        existing = (self.db.query(models.Application)
                    .filter_by(user_id=self.user.id, opportunity_id=opp.id).first())
        if existing is not None:
            return self._app_out(existing, opp), False

        if opp.kind == "vacancy" and job is not None:
            company = job.company_name or (org.name if org else "") or ""
            role = job.title or opp.title or ""
            location = job.location or (org.location if org else None)
            job_url = job.source_url
            raw_jd = job.raw_text or opp.description or ""
        else:
            company = (org.name if org else "") or ""
            role = ""  # no vacancy: no invented title, no synthetic JD
            location = org.location if org else None
            job_url = org.website if org else None  # company site — not a job URL
            raw_jd = ""

        obj = models.Application(
            user_id=self.user.id, opportunity_id=opp.id, job_id=opp.job_id,
            company=company, role=role, location=location, job_url=job_url,
            date_saved=date.today().isoformat(), status="saved",
            status_history=[{"to": "saved", "at": _now_iso()}],
            raw_jd=raw_jd,
        )
        self.db.add(obj)
        try:
            self.db.commit()
        except IntegrityError:
            # Concurrent save raced us — the unique index allowed only one.
            self.db.rollback()
            existing = (self.db.query(models.Application)
                        .filter_by(user_id=self.user.id, opportunity_id=opp.id).first())
            return self._app_out(existing, opp), False
        self.db.refresh(obj)
        return self._app_out(obj, opp), True

    def _app_out(self, app: models.Application, opp: models.Opportunity) -> dict:
        return {
            "id": app.id, "opportunity_id": opp.id, "kind": opp.kind,
            "company": app.company, "role": app.role, "location": app.location,
            "job_url": app.job_url, "status": app.status,
            "date_saved": app.date_saved,
            "has_listing": opp.kind == "vacancy",
            "raw_jd": app.raw_jd,  # empty for prospects — never fabricated
            "status_history": app.status_history or [],
            "created_at": app.created_at.isoformat() if app.created_at else None,
        }
