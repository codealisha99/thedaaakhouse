"""Discovery endpoints — sources, inline scans, listings (spec §9).

Manual scans execute inline and return the finished run; the durable task
API supersedes this once step-02 execution lands. Other-owner objects are
404, not 403 (spec §9).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import models
from app.db.database import get_db
from app.discovery import service
from app.discovery.adapters import SourceConfigError
from app.discovery.service import SourceScanConflict
from app.schemas.discovery import (
    ListingOut,
    ListingSourceOut,
    RunCreate,
    RunOut,
    SourceCreate,
    SourceOut,
    SourcePatch,
)

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


def _source_out(source) -> SourceOut:
    return SourceOut(
        id=source.id,
        name=source.name,
        adapter=source.adapter,
        config=source.config or {},
        enabled=source.enabled,
        interval_minutes=source.interval_minutes,
        max_listings=source.max_listings,
        next_run_at=source.next_run_at,
        last_run_at=source.last_run_at,
        last_success_at=source.last_success_at,
        consecutive_failures=source.consecutive_failures,
        created_at=source.created_at,
    )


def _listing_out(db: Session, listing) -> ListingOut:
    links = service.listing_sources(db, listing.id)
    return ListingOut(
        id=listing.id,
        status=listing.status,
        title=listing.title,
        company_name=listing.company_name,
        location=listing.location,
        remote_mode=listing.remote_mode,
        employment_type=listing.employment_type,
        posted_at=listing.posted_at,
        first_seen_at=listing.first_seen_at,
        last_seen_at=listing.last_seen_at,
        closed_at=listing.closed_at,
        closed_reason=listing.closed_reason,
        canonical_url=listing.canonical_url,
        apply_url=listing.apply_url,
        needs_review=listing.needs_review,
        review_candidate_id=listing.review_candidate_id,
        sources=[
            ListingSourceOut(
                source_id=link.source_id,
                external_id=link.external_id,
                source_url=link.source_url,
                apply_url=link.apply_url,
                posted_at=link.posted_at,
                first_seen_at=link.first_seen_at,
                last_seen_at=link.last_seen_at,
                match_method=link.match_method,
                match_score=link.match_score,
            )
            for link in links
        ],
    )


# ------------------------------------------------------------------ sources

@router.post("/sources", status_code=201)
def create_source(
    payload: SourceCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        source = service.create_source(
            db,
            user.id,
            name=payload.name,
            adapter=payload.adapter,
            config=payload.config,
            interval_minutes=payload.interval_minutes,
            max_listings=payload.max_listings,
            enabled=payload.enabled,
        )
    except SourceConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _source_out(source)


@router.get("/sources")
def list_sources(
    enabled: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return [_source_out(s) for s in service.list_sources(db, user.id, enabled=enabled)]


@router.get("/sources/{source_id}")
def get_source(
    source_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    source = service.get_source(db, user.id, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="discovery source not found")
    return _source_out(source)


@router.patch("/sources/{source_id}")
def patch_source(
    source_id: str,
    payload: SourcePatch,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    source = service.get_source(db, user.id, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="discovery source not found")
    fields = payload.model_dump(exclude_unset=True)
    try:
        source = service.update_source(db, source, **fields)
    except SourceConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _source_out(source)


# ---------------------------------------------------------------------- runs

@router.post("/runs", status_code=201)
def start_run(
    payload: RunCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        run = service.run_scan(db, user.id, payload.source_id, trigger="manual")
    except LookupError:
        raise HTTPException(status_code=404, detail="discovery source not found")
    except SourceScanConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    return RunOut.model_validate(run)


@router.get("/runs")
def list_runs(
    source_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return [
        RunOut.model_validate(r)
        for r in service.list_runs(db, user.id, source_id=source_id)
    ]


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    run = service.get_run(db, user.id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="discovery run not found")
    return RunOut.model_validate(run)


# ------------------------------------------------------------------ listings

@router.get("/listings")
def list_listings(
    status: str | None = Query(default=None, pattern="^(active|closed)$"),
    needs_review: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    items = service.list_listings(db, user.id, status=status, needs_review=needs_review)
    return [_listing_out(db, listing) for listing in items]


@router.get("/listings/{listing_id}")
def get_listing(
    listing_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    listing = service.get_listing(db, user.id, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="job listing not found")
    return _listing_out(db, listing)
