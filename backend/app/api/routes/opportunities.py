"""Opportunities — ranking, startup prospects, evidence and idempotent save.

Eligibility, fit and competition evidence stay separate everywhere; a
no-vacancy prospect saves with no fake job description; saving the same
opportunity twice returns the same application.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import models
from app.db.database import get_db
from app.opportunities.providers import (
    available_providers,
    get_startup_search_provider,
)
from app.opportunities.service import OpportunityService
from app.schemas.opportunity import (
    ApplicantCountIn,
    EvaluateIn,
    ExcludeIn,
    OpportunityDetailOut,
    OpportunityListOut,
    SaveResultOut,
    StartupCreateIn,
    StartupSearchIn,
    StartupSearchOut,
    ProvidersOut,
    VacancyCreateIn,
)

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


def _svc(db: Session, user: models.User) -> OpportunityService:
    return OpportunityService(db, user)


@router.post("", status_code=201)
def create_vacancy(payload: VacancyCreateIn, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    """Create a vacancy opportunity from an existing job listing, then evaluate."""
    try:
        opp = _svc(db, user).create_vacancy(payload.job_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _detail(opp.id, db, user)




@router.post("/startups", status_code=201)
def create_startup(payload: StartupCreateIn, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    """Create a startup prospect from a user-supplied URL. No vacancy, no
    synthetic JD — the URL itself is the source evidence."""
    try:
        opp = _svc(db, user).create_prospect(payload.url, name=payload.name, note=payload.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _detail(opp.id, db, user)


@router.get("/providers")
def list_providers():
    from app.core.config import get_settings

    return ProvidersOut(configured=get_settings().startup_search_provider,
                        available=available_providers()).model_dump()


@router.post("/startups/search")
def search_startups(payload: StartupSearchIn, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    """Search the configured startup-search provider. Leads are returned, never
    auto-created; pick one and POST /api/opportunities/startups to save it."""
    profile = _svc(db, user)._profile_dict()
    provider = get_startup_search_provider()
    leads = provider.search(payload.query, profile, payload.limit)
    from app.core.config import get_settings

    return StartupSearchOut(provider=provider.name,
                            configured=get_settings().startup_search_provider,
                            leads=leads).model_dump()


@router.get("")
def list_opportunities(
    kind: str | None = Query(default=None),
    eligibility: str | None = Query(default=None),
    fit: str | None = Query(default=None),
    competition: str | None = Query(default=None),
    max_applicants: int | None = Query(default=None, ge=0),
    max_age_days: int = Query(default=30, ge=1, le=365),
    overlooked: bool | None = Query(default=None),
    min_priority: float | None = Query(default=None, ge=0, le=100),
    include_excluded: bool = Query(default=False),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        return _svc(db, user).list(
            kind=kind, eligibility=eligibility, fit=fit, competition=competition,
            max_applicants=max_applicants, max_age_days=max_age_days,
            overlooked=overlooked, min_priority=min_priority,
            include_excluded=include_excluded, cursor=cursor, limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{opportunity_id}")
def get_opportunity(opportunity_id: str, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    try:
        return _detail(opportunity_id, db, user)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{opportunity_id}/evaluate")
def evaluate(opportunity_id: str, payload: EvaluateIn,
             db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Run (or re-run) ranking. Weights are validated; each run is a new
    versioned snapshot with contributions and coverage."""
    try:
        return _svc(db, user).evaluate(opportunity_id, weights=payload.weights)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{opportunity_id}/exclude")
def exclude(opportunity_id: str, payload: ExcludeIn,
            db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    try:
        return _svc(db, user).exclude(opportunity_id, payload.excluded, payload.reason)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{opportunity_id}/applicant-count", status_code=201)
def record_applicant_count(opportunity_id: str, payload: ApplicantCountIn,
                           db: Session = Depends(get_db),
                           user: models.User = Depends(get_current_user)):
    """Record an observed applicant count with source, time and measurement
    meaning, then refresh the versioned evaluation. Clicks/views are stored
    as non-comparable measurements, not as application counts."""
    try:
        return _svc(db, user).record_applicant_count(
            opportunity_id, payload.count, platform=payload.platform,
            source=payload.source, observed_at=payload.observed_at,
            meaning=payload.meaning, note=payload.note,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{opportunity_id}/save")
def save_opportunity(opportunity_id: str, db: Session = Depends(get_db),
                     user: models.User = Depends(get_current_user)):
    """Idempotently link the opportunity to a tracked application. A second
    save returns the same application with created=false (HTTP 200)."""
    try:
        app, created = _svc(db, user).save(opportunity_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    body = SaveResultOut(application=app, created=created).model_dump()
    return JSONResponse(content=body, status_code=201 if created else 200)


def _detail(opportunity_id: str, db: Session, user: models.User) -> dict:
    out = OpportunityService(db, user).get(opportunity_id)
    return OpportunityDetailOut(**out).model_dump()
