"""Discovery scan engine: source CRUD, scan execution, listing lifecycle.

Invariants (spec §3, §7):
- A failed or truncated fetch never closes listings and never counts as an
  absent observation; only a *successful complete* scan increments
  `absent_scans`.
- Closure needs `discovery_scan_absent_threshold` consecutive complete scans
  without the listing; the rule name is stored on `closed_reason`.
- Fresh evidence reopens a closed listing (repost) without losing history.
- Manual scans run inline; a scan of a source that is already running
  conflicts (409 at the API layer).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.discovery.adapters import (
    ADAPTERS,
    AdapterError,
    AdapterResult,
    BaseAdapter,
    Fetcher,
    ObservedJob,
    SourceConfigError,
    get_adapter_class,
)
from app.discovery.config import get_discovery_settings
from app.discovery.dedup import Match, find_match
from app.discovery.models import (
    DiscoveryRun,
    DiscoverySource,
    JobListing,
    ListingSource,
)
from app.discovery.normalize import (
    canonicalize_url,
    content_hash,
    detect_remote_mode,
    validate_source_url,
)

MAX_ERROR_DETAIL = 500
_BACKOFF_CAP = timedelta(hours=24)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceScanConflict(Exception):
    """A scan of this source is already running."""


def default_fetcher() -> Fetcher:
    """Live fetcher through the centralized safe fetcher (lazy import so
    tests never load network code)."""
    from app.ingestion.safe_fetch import FetchPolicy, safe_fetch

    s = get_discovery_settings()
    policy = FetchPolicy(
        timeout_s=s.discovery_fetch_timeout_s,
        max_bytes=s.discovery_fetch_max_bytes,
        max_redirects=s.discovery_fetch_max_redirects,
    )

    def fetch(url: str):
        return safe_fetch(url, policy=policy)

    return fetch


# ------------------------------------------------------------------ sources

def validate_adapter_config(adapter_name: str, config: dict) -> dict:
    adapter_cls = get_adapter_class(adapter_name)  # SourceConfigError if unknown
    return adapter_cls.validate_config(config or {})


def _validate_fetch_url(url: str) -> None:
    """URL policy failures are config errors at the API boundary (HTTP 400)."""
    try:
        validate_source_url(url)
    except ValueError as e:
        raise SourceConfigError(str(e)) from e


def create_source(
    db: Session,
    owner_id: str,
    *,
    name: str,
    adapter: str,
    config: dict,
    interval_minutes: int = 720,
    max_listings: int = 100,
    enabled: bool = True,
) -> DiscoverySource:
    cfg = validate_adapter_config(adapter, config)
    if adapter == "company_careers":
        _validate_fetch_url(cfg["url"])
    now = utcnow()
    source = DiscoverySource(
        owner_id=owner_id,
        name=name.strip(),
        adapter=adapter,
        config=cfg,
        enabled=enabled,
        interval_minutes=interval_minutes,
        max_listings=max_listings,
        next_run_at=now + timedelta(minutes=interval_minutes) if enabled else None,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def update_source(db: Session, source: DiscoverySource, **fields) -> DiscoverySource:
    now = utcnow()
    if "config" in fields and fields["config"] is not None:
        source.config = validate_adapter_config(source.adapter, fields["config"])
        if source.adapter == "company_careers":
            _validate_fetch_url(source.config["url"])
    if "name" in fields and fields["name"] is not None:
        source.name = fields["name"].strip()
    if "interval_minutes" in fields and fields["interval_minutes"] is not None:
        source.interval_minutes = fields["interval_minutes"]
    if "max_listings" in fields and fields["max_listings"] is not None:
        source.max_listings = fields["max_listings"]
    if "enabled" in fields and fields["enabled"] is not None:
        source.enabled = fields["enabled"]
    source.next_run_at = (
        now + timedelta(minutes=source.interval_minutes) if source.enabled else None
    )
    db.commit()
    db.refresh(source)
    return source


def get_source(db: Session, owner_id: str, source_id: str) -> DiscoverySource | None:
    return db.execute(
        select(DiscoverySource).where(
            DiscoverySource.id == source_id, DiscoverySource.owner_id == owner_id
        )
    ).scalar_one_or_none()


def list_sources(
    db: Session, owner_id: str, *, enabled: bool | None = None, limit: int = 100, offset: int = 0
) -> list[DiscoverySource]:
    stmt = select(DiscoverySource).where(DiscoverySource.owner_id == owner_id)
    if enabled is not None:
        stmt = stmt.where(DiscoverySource.enabled == enabled)
    stmt = stmt.order_by(DiscoverySource.created_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars())


# ---------------------------------------------------------------------- runs

def get_run(db: Session, owner_id: str, run_id: str) -> DiscoveryRun | None:
    return db.execute(
        select(DiscoveryRun).where(
            DiscoveryRun.id == run_id, DiscoveryRun.owner_id == owner_id
        )
    ).scalar_one_or_none()


def list_runs(
    db: Session, owner_id: str, *, source_id: str | None = None, limit: int = 50, offset: int = 0
) -> list[DiscoveryRun]:
    stmt = select(DiscoveryRun).where(DiscoveryRun.owner_id == owner_id)
    if source_id:
        stmt = stmt.where(DiscoveryRun.source_id == source_id)
    stmt = stmt.order_by(DiscoveryRun.started_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars())


def run_scan(
    db: Session,
    owner_id: str,
    source_id: str,
    *,
    trigger: str = "manual",
    fetcher: Fetcher | None = None,
) -> DiscoveryRun:
    """Execute one scan inline. Raises SourceScanConflict if one is active,
    LookupError if the source is missing/foreign."""
    source = get_source(db, owner_id, source_id)
    if source is None:
        raise LookupError("discovery source not found")
    active = db.execute(
        select(DiscoveryRun).where(
            DiscoveryRun.source_id == source.id, DiscoveryRun.status == "running"
        )
    ).scalars().first()
    if active is not None:
        raise SourceScanConflict("a scan of this source is already running")

    now = utcnow()
    run = DiscoveryRun(
        source_id=source.id,
        owner_id=owner_id,
        status="running",
        trigger=trigger,
        started_at=now,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    fetch = fetcher or default_fetcher()
    try:
        adapter_cls: type[BaseAdapter] = get_adapter_class(source.adapter)
        adapter = adapter_cls(fetch)
        result = adapter.discover(source.config or {}, source.cursor, source.max_listings)
        _process_result(db, source, run, result)
        source.cursor = result.cursor
        source.last_run_at = utcnow()
        source.last_success_at = utcnow()
        source.consecutive_failures = 0
        source.next_run_at = utcnow() + timedelta(minutes=source.interval_minutes)
        run.status = "succeeded"
        run.finished_at = utcnow()
        db.commit()
    except Exception as e:  # noqa: BLE001 — every failure fails the run, not listings
        db.rollback()
        run = db.get(DiscoveryRun, run.id)
        source = db.get(DiscoverySource, source.id)
        if run is not None:
            run.status = "failed"
            run.finished_at = utcnow()
            run.error_code = getattr(e, "code", None) or "internal_error"
            run.error_detail = str(e)[:MAX_ERROR_DETAIL]
        if source is not None:
            source.consecutive_failures = (source.consecutive_failures or 0) + 1
            source.last_run_at = utcnow()
            backoff = min(
                timedelta(minutes=source.interval_minutes)
                * (2 ** min(source.consecutive_failures, 4)),
                _BACKOFF_CAP,
            )
            source.next_run_at = utcnow() + backoff
        db.commit()
    db.refresh(run)
    return run


def _process_result(
    db: Session, source: DiscoverySource, run: DiscoveryRun, result: AdapterResult
) -> None:
    """Upsert observations and (only on complete scans) apply absence rules."""
    settings = get_discovery_settings()
    now = utcnow()
    seen_external: set[str] = set()
    seen_urls: set[str] = set()
    created = updated = review = 0

    for job in result.jobs:
        run.seen_count += 1
        if job.external_id:
            seen_external.add(job.external_id)
        url = canonicalize_url(job.source_url)
        if url:
            seen_urls.add(url)
        was_created, was_updated, was_review = _upsert_observation(db, source, job, now)
        created += int(was_created)
        updated += int(was_updated)
        review += int(was_review)

    closed = 0
    if result.complete:
        closed = _apply_absence_rules(db, source, seen_external, seen_urls, now,
                                      threshold=max(1, settings.discovery_scan_absent_threshold))

    run.pages_fetched = int((result.diagnostics or {}).get("pages") or 0)
    run.created_count = created
    run.updated_count = updated
    run.closed_count = closed
    run.review_count = review


def _upsert_observation(
    db: Session, source: DiscoverySource, job: ObservedJob, now: datetime
) -> tuple[bool, bool, bool]:
    """Returns (created_listing, updated_listing, flagged_review)."""
    match: Match = find_match(db, source.owner_id, source, job)
    canonical = canonicalize_url(job.source_url)
    apply_canonical = canonicalize_url(job.apply_url) or canonical
    hashed = content_hash(job.title, job.company_name, job.location, job.description)

    if match.listing is None:
        listing = JobListing(
            owner_id=source.owner_id,
            status="active",
            title=job.title.strip(),
            company_name=(job.company_name or (source.config or {}).get("company_name")
                          or source.name).strip(),
            location=job.location,
            remote_mode=job.remote_mode or detect_remote_mode(job.location),
            employment_type=job.employment_type,
            description=job.description,
            posted_at=job.posted_at,
            first_seen_at=now,
            last_seen_at=now,
            canonical_url=canonical,
            apply_url=apply_canonical,
            content_hash=hashed,
            needs_review=match.needs_review,
            review_candidate_id=match.review_candidate.id if match.review_candidate else None,
        )
        db.add(listing)
        db.flush()
        _add_link(db, listing, source, job, canonical, apply_canonical, hashed, match, now)
        return True, False, match.needs_review

    listing = match.listing
    _add_link(db, listing, source, job, canonical, apply_canonical, hashed, match, now)
    if listing.status == "closed":
        # Fresh evidence: reopen (repost preserves the same listing row).
        listing.status = "active"
        listing.closed_at = None
        listing.closed_reason = None
        listing.absent_scans = 0
    if listing.absent_scans:
        listing.absent_scans = 0  # presence in any scan resets the counter
    listing.last_seen_at = now
    if listing.posted_at is None and job.posted_at is not None:
        listing.posted_at = job.posted_at
    if listing.description is None and job.description:
        listing.description = job.description
    if listing.location is None and job.location:
        listing.location = job.location
    if listing.remote_mode is None and job.remote_mode:
        listing.remote_mode = job.remote_mode
    if listing.canonical_url is None and canonical:
        listing.canonical_url = canonical
    # Re-observing an existing listing counts as an update of that listing.
    return False, True, False


def _add_link(
    db: Session,
    listing: JobListing,
    source: DiscoverySource,
    job: ObservedJob,
    canonical: str | None,
    apply_canonical: str | None,
    hashed: str,
    match: Match,
    now: datetime,
) -> bool:
    """Attach (or refresh) this source's link to the listing."""
    link = db.execute(
        select(ListingSource).where(
            ListingSource.source_id == source.id,
            ListingSource.listing_id == listing.id,
        )
    ).scalar_one_or_none()
    if link is not None:
        link.last_seen_at = now
        link.content_hash = hashed
        if job.external_id and not link.external_id:
            link.external_id = job.external_id
        if apply_canonical:
            link.apply_url = apply_canonical
        return False
    link = ListingSource(
        listing_id=listing.id,
        source_id=source.id,
        external_id=(job.external_id or None),
        source_url=canonical or job.source_url,
        apply_url=apply_canonical,
        posted_at=job.posted_at,
        first_seen_at=now,
        last_seen_at=now,
        content_hash=hashed,
        match_method=match.method,
        match_score=match.score,
    )
    db.add(link)
    return True


def _apply_absence_rules(
    db: Session,
    source: DiscoverySource,
    seen_external: set[str],
    seen_urls: set[str],
    now: datetime,
    *,
    threshold: int,
) -> int:
    """Close listings absent from this *complete* scan. Returns closed count."""
    links = db.execute(
        select(ListingSource).where(ListingSource.source_id == source.id)
    ).scalars().all()
    closed = 0
    for link in links:
        listing = link.listing
        if listing is None or listing.status != "active":
            continue
        if link.external_id:
            present = link.external_id in seen_external
        else:
            present = canonicalize_url(link.source_url) in seen_urls
        if present:
            if listing.absent_scans:
                listing.absent_scans = 0
            continue
        listing.absent_scans = (listing.absent_scans or 0) + 1
        if listing.absent_scans >= threshold:
            listing.status = "closed"
            listing.closed_at = now
            listing.closed_reason = "absent_complete_scans"
            listing.absent_scans = 0
            closed += 1
    return closed


# ------------------------------------------------------------------ listings

def list_listings(
    db: Session,
    owner_id: str,
    *,
    status: str | None = None,
    needs_review: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[JobListing]:
    stmt = select(JobListing).where(JobListing.owner_id == owner_id)
    if status is not None:
        stmt = stmt.where(JobListing.status == status)
    if needs_review is not None:
        stmt = stmt.where(JobListing.needs_review == needs_review)
    stmt = stmt.order_by(JobListing.first_seen_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars())


def get_listing(db: Session, owner_id: str, listing_id: str) -> JobListing | None:
    return db.execute(
        select(JobListing).where(
            JobListing.id == listing_id, JobListing.owner_id == owner_id
        )
    ).scalar_one_or_none()


def listing_sources(db: Session, listing_id: str) -> list[ListingSource]:
    return list(
        db.execute(
            select(ListingSource).where(ListingSource.listing_id == listing_id)
        ).scalars()
    )


def due_sources(db: Session, *, now: datetime | None = None, limit: int = 5) -> list[DiscoverySource]:
    """Enabled sources whose next_run_at is due (scheduler tick)."""
    now = now or utcnow()
    return list(
        db.execute(
            select(DiscoverySource)
            .where(DiscoverySource.enabled.is_(True), DiscoverySource.next_run_at <= now)
            .order_by(DiscoverySource.next_run_at)
            .limit(limit)
        ).scalars()
    )


__all__ = [
    "ADAPTERS",
    "AdapterError",
    "SourceConfigError",
    "SourceScanConflict",
    "create_source",
    "default_fetcher",
    "due_sources",
    "get_listing",
    "get_run",
    "get_source",
    "list_listings",
    "list_runs",
    "list_sources",
    "listing_sources",
    "run_scan",
    "update_source",
    "validate_adapter_config",
]
