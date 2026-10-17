"""Step 03 — scheduled job discovery: adapters, dedup, lifecycle, API.

All network access goes through injected stub fetchers; nothing here
touches the real Greenhouse/Lever/careers endpoints or safe_fetch.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.discovery import service
from app.discovery.adapters import AdapterError, SourceConfigError, get_adapter_class
from app.discovery.models import DiscoveryRun, DiscoverySource, JobListing, ListingSource
from app.discovery.normalize import canonicalize_url, validate_source_url
from app.discovery.scheduler import DiscoveryScheduler

USER_ID = "11111111-1111-1111-1111-111111111111"
OTHER_USER_ID = "22222222-2222-2222-2222-222222222222"


# ------------------------------------------------------------------ fixtures

@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'disc.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    from app.core.config import get_settings

    get_settings.cache_clear()

    import app.db.models  # noqa: F401 — register users table
    import app.discovery.models  # noqa: F401

    eng = create_engine(url, connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=eng)
    db = TestingSession()
    from app.db import models

    db.add(models.User(id=USER_ID, username="owner", password_hash="x"))
    db.add(models.User(id=OTHER_USER_ID, username="other", password_hash="x"))
    db.commit()
    yield db
    db.close()


class _StubResponse:
    def __init__(self, content: bytes, url: str = ""):
        self.status_code = 200
        self.url = url
        self.headers: dict = {}
        self.content = content


def stub_fetcher(mapping: dict):
    """URL-prefix -> bytes | Exception. First matching prefix wins."""

    def fetch(url: str):
        for prefix, payload in mapping.items():
            if url.startswith(prefix):
                if isinstance(payload, Exception):
                    raise payload
                return _StubResponse(payload, url)
        raise AssertionError(f"stub has no route for {url}")

    return fetch


def gh_payload(jobs: list[dict], total: int | None = None) -> bytes:
    meta = {"total": total if total is not None else len(jobs)}
    return json.dumps({"jobs": jobs, "meta": meta}).encode()


def gh_job(job_id, title, url, location="New York, NY", content="Build things"):
    return {
        "id": job_id,
        "title": title,
        "absolute_url": url,
        "location": {"name": location},
        "content": content,
        "updated_at": "2026-10-01T00:00:00Z",
    }


def careers_html(title, url, company="Acme", location="New York, NY"):
    node = {
        "@type": "JobPosting",
        "title": title,
        "url": url,
        "description": "Build things at Acme.",
        "hiringOrganization": {"name": company},
        "jobLocation": {"address": {"addressLocality": location}},
    }
    return (
        "<html><head></head><body><h1>Careers</h1>"
        f'<script type="application/ld+json">{json.dumps(node)}</script>'
        "</body></html>"
    ).encode()


def make_source(db, owner_id=USER_ID, adapter="greenhouse", config=None, **kw):
    config = config if config is not None else {"board_token": "acme"}
    return service.create_source(
        db, owner_id, name=kw.pop("name", "Acme board"), adapter=adapter,
        config=config, **kw,
    )


def listings(db, owner_id=USER_ID):
    return list(db.execute(select(JobListing).where(JobListing.owner_id == owner_id)).scalars())


def links(db, listing_id):
    return list(db.execute(select(ListingSource).where(ListingSource.listing_id == listing_id)).scalars())


# ------------------------------------------------------------------ adapters

def test_greenhouse_adapter_parses_jobs():
    adapter = get_adapter_class("greenhouse")(stub_fetcher({
        "https://boards-api.greenhouse.io/": gh_payload([
            gh_job(101, "Backend Engineer", "https://boards.greenhouse.io/acme/jobs/101"),
        ]),
    }))
    result = adapter.discover({"board_token": "acme"}, None, 50)
    assert result.complete is True
    job = result.jobs[0]
    assert job.external_id == "101"
    assert job.title == "Backend Engineer"
    assert job.posted_at is None  # updated_at is not a posting date (spec)
    assert "Build things" in (job.description or "")


def test_greenhouse_adapter_maps_fetch_failure_to_adapter_error():
    adapter = get_adapter_class("greenhouse")(stub_fetcher({
        "https://boards-api.greenhouse.io/": ConnectionError("boom"),
    }))
    with pytest.raises(AdapterError) as exc:
        adapter.discover({"board_token": "acme"}, None, 50)
    assert exc.value.code in ("source_unavailable", "blocked_url")


def test_lever_adapter_parses_and_posts_dated():
    posting = {
        "id": "uuid-1",
        "text": "ML Engineer",
        "hostedUrl": "https://jobs.lever.co/acme/uuid-1",
        "descriptionPlain": "Model things",
        "createdAt": 1_727_740_800_000,  # epoch ms
        "location": {"name": "Remote - US"},
        "workplaceType": "remote",
    }
    adapter = get_adapter_class("lever")(stub_fetcher({
        "https://api.lever.co/": json.dumps([posting]).encode(),
    }))
    result = adapter.discover({"org": "acme"}, None, 50)
    job = result.jobs[0]
    assert job.external_id == "uuid-1"
    assert job.posted_at is not None
    assert job.remote_mode == "remote"


def test_company_careers_parses_jsonld():
    url = "https://acme.example/careers/senior-backend"
    adapter = get_adapter_class("company_careers")(stub_fetcher({
        "https://acme.example/careers": careers_html("Senior Backend Engineer", url),
    }))
    result = adapter.discover({"url": "https://acme.example/careers", "company_name": "Acme"}, None, 50)
    assert result.complete is True
    job = result.jobs[0]
    assert job.title == "Senior Backend Engineer"
    assert job.company_name == "Acme"
    assert "New York" in (job.location or "")


def test_company_careers_zero_jobs_fails_scan():
    adapter = get_adapter_class("company_careers")(stub_fetcher({
        "https://acme.example/careers": b"<html><body><h1>Careers</h1><p>Nothing here</p></body></html>",
    }))
    with pytest.raises(AdapterError) as exc:
        adapter.discover({"url": "https://acme.example/careers"}, None, 50)
    assert exc.value.code == "no_jobs_parsed"


def test_company_careers_allow_empty_succeeds():
    adapter = get_adapter_class("company_careers")(stub_fetcher({
        "https://acme.example/careers": b"<html><body>no jobs</body></html>",
    }))
    result = adapter.discover(
        {"url": "https://acme.example/careers", "allow_empty": True}, None, 50
    )
    assert result.complete is True
    assert result.jobs == []


# ------------------------------------------------------- config and URL safety

def test_create_source_validates_config(db_session):
    with pytest.raises(SourceConfigError):
        make_source(db_session, config={"board_token": "bad token!"})
    with pytest.raises(SourceConfigError):
        make_source(db_session, adapter="lever", config={})
    with pytest.raises(SourceConfigError):
        make_source(db_session, adapter="company_careers",
                    config={"url": "http://127.0.0.1/careers"})

@pytest.mark.parametrize("bad_url", [
    "file:///etc/passwd",
    "http://127.0.0.1:8000/careers",
    "http://10.0.0.5/jobs",
    "http://192.168.1.10/jobs",
    "http://[::1]/jobs",
    "http://user:pass@acme.example/careers",
    "ftp://acme.example/careers",
])
def test_validate_source_url_rejects_unsafe(bad_url):
    with pytest.raises(ValueError):
        validate_source_url(bad_url)


def test_validate_source_url_accepts_public_https():
    assert validate_source_url("https://acme.example/careers") == "https://acme.example/careers"


def test_canonicalize_strips_tracking_params():
    url = "https://acme.example/jobs/1?utm_source=board&utm_medium=x&gclid=abc&id=keep"
    assert canonicalize_url(url) == "https://acme.example/jobs/1?id=keep"


# ------------------------------------------------------------- scan lifecycle

def test_scan_creates_listings_and_counts(db_session):
    source = make_source(db_session)
    fetcher = stub_fetcher({
        "https://boards-api.greenhouse.io/": gh_payload([
            gh_job(1, "Backend Engineer", "https://boards.greenhouse.io/acme/jobs/1"),
            gh_job(2, "Frontend Engineer", "https://boards.greenhouse.io/acme/jobs/2"),
        ]),
    })
    run = service.run_scan(db_session, USER_ID, source.id, fetcher=fetcher)
    assert run.status == "succeeded", f"{run.error_code}: {run.error_detail}"
    assert run.seen_count == 2
    assert run.created_count == 2
    assert run.closed_count == 0
    assert len(listings(db_session)) == 2
    db_session.refresh(source)
    assert source.consecutive_failures == 0
    assert source.next_run_at is not None


def test_same_source_rescan_updates_not_duplicates(db_session):
    source = make_source(db_session)
    payload = gh_payload([gh_job(1, "Backend Engineer", "https://boards.greenhouse.io/acme/jobs/1")])
    fetcher = stub_fetcher({"https://boards-api.greenhouse.io/": payload})
    service.run_scan(db_session, USER_ID, source.id, fetcher=fetcher)
    run2 = service.run_scan(db_session, USER_ID, source.id, fetcher=fetcher)
    assert run2.status == "succeeded"
    assert run2.created_count == 0
    assert run2.updated_count >= 1
    assert len(listings(db_session)) == 1


def test_cross_site_same_job_becomes_one_listing(db_session):
    """Spec acceptance: the same job from two different sites is one listing."""
    url = "https://boards.greenhouse.io/acme/jobs/1"
    gh = make_source(db_session, name="Acme GH", adapter="greenhouse",
                     config={"board_token": "acme", "company_name": "Acme"})
    careers = make_source(db_session, name="Acme careers", adapter="company_careers",
                          config={"url": "https://acme.example/careers",
                                  "company_name": "Acme", "domain": "acme.example"})
    service.run_scan(db_session, USER_ID, gh.id, fetcher=stub_fetcher({
        "https://boards-api.greenhouse.io/": gh_payload([gh_job(1, "Senior Backend Engineer", url, "New York, NY")]),
    }))
    service.run_scan(db_session, USER_ID, careers.id, fetcher=stub_fetcher({
        "https://acme.example/careers": careers_html(
            "Senior Backend Engineer", "https://acme.example/careers/senior-backend", "Acme", "New York, NY"
        ),
    }))
    rows = listings(db_session)
    assert len(rows) == 1
    listing = rows[0]
    assert len(links(db_session, listing.id)) == 2  # both sources preserved


def test_same_external_id_across_boards_merges(db_session):
    board_a = make_source(db_session, name="A", config={"board_token": "boarda"})
    board_b = make_source(db_session, name="B", config={"board_token": "boardb"})
    job = gh_job(777, "Platform Engineer", "https://boards.greenhouse.io/boarda/jobs/777")
    service.run_scan(db_session, USER_ID, board_a.id,
                     fetcher=stub_fetcher({"https://boards-api.greenhouse.io/": gh_payload([job])}))
    service.run_scan(db_session, USER_ID, board_b.id,
                     fetcher=stub_fetcher({"https://boards-api.greenhouse.io/": gh_payload([job])}))
    rows = listings(db_session)
    assert len(rows) == 1
    assert len(links(db_session, rows[0].id)) == 2


def test_fuzzy_uncertain_title_goes_to_review(db_session):
    gh = make_source(db_session, name="Acme GH", adapter="greenhouse",
                     config={"board_token": "acme", "company_name": "Acme"})
    careers = make_source(db_session, name="Acme careers", adapter="company_careers",
                          config={"url": "https://acme.example/careers",
                                  "company_name": "Acme", "domain": "acme.example"})
    service.run_scan(db_session, USER_ID, gh.id, fetcher=stub_fetcher({
        "https://boards-api.greenhouse.io/": gh_payload([
            gh_job(1, "Senior Backend Engineer", "https://boards.greenhouse.io/acme/jobs/1", "New York, NY"),
        ]),
    }))
    # Near-miss title on a different URL: uncertain, must not auto-merge.
    service.run_scan(db_session, USER_ID, careers.id, fetcher=stub_fetcher({
        "https://acme.example/careers": careers_html(
            "Senior Backend Developer", "https://acme.example/careers/senior-backend-dev", "Acme", "New York, NY"
        ),
    }))
    rows = listings(db_session)
    assert len(rows) == 2
    flagged = [r for r in rows if r.needs_review]
    assert len(flagged) == 1
    assert flagged[0].review_candidate_id is not None


def test_failed_fetch_never_closes_or_counts_absence(db_session):
    source = make_source(db_session)
    good = stub_fetcher({"https://boards-api.greenhouse.io/": gh_payload([
        gh_job(1, "Backend Engineer", "https://boards.greenhouse.io/acme/jobs/1"),
    ])})
    service.run_scan(db_session, USER_ID, source.id, fetcher=good)
    listing = listings(db_session)[0]

    failed = stub_fetcher({"https://boards-api.greenhouse.io/": ConnectionError("down")})
    run = service.run_scan(db_session, USER_ID, source.id, fetcher=failed)
    assert run.status == "failed"
    assert run.error_code is not None

    db_session.refresh(listing)
    assert listing.status == "active"
    assert listing.absent_scans == 0
    assert listing.closed_at is None
    assert listing.closed_reason is None


def test_failure_increments_backoff(db_session):
    source = make_source(db_session, interval_minutes=60)
    # SQLite returns naive datetimes; compare against a naive baseline.
    before = service.utcnow().replace(tzinfo=None)
    run = service.run_scan(db_session, USER_ID, source.id, fetcher=stub_fetcher({
        "https://boards-api.greenhouse.io/": ConnectionError("down"),
    }))
    assert run.status == "failed"
    db_session.refresh(source)
    assert source.consecutive_failures == 1
    assert source.next_run_at > before + timedelta(minutes=60)  # backoff beyond interval


def test_absence_closes_after_threshold(db_session, monkeypatch):
    monkeypatch.setenv("DISCOVERY_SCAN_ABSENT_THRESHOLD", "3")
    from app.discovery.config import get_discovery_settings

    get_discovery_settings.cache_clear()
    try:
        source = make_source(db_session)
        full = stub_fetcher({"https://boards-api.greenhouse.io/": gh_payload([
            gh_job(1, "Backend Engineer", "https://boards.greenhouse.io/acme/jobs/1"),
        ])})
        empty = stub_fetcher({"https://boards-api.greenhouse.io/": gh_payload([])})
        service.run_scan(db_session, USER_ID, source.id, fetcher=full)
        listing = listings(db_session)[0]

        for expected in (1, 2):
            run = service.run_scan(db_session, USER_ID, source.id, fetcher=empty)
            assert run.status == "succeeded"
            assert run.closed_count == 0
            db_session.refresh(listing)
            assert listing.status == "active"
            assert listing.absent_scans == expected

        run = service.run_scan(db_session, USER_ID, source.id, fetcher=empty)
        assert run.closed_count == 1
        db_session.refresh(listing)
        assert listing.status == "closed"
        assert listing.closed_reason == "absent_complete_scans"
        assert listing.absent_scans == 0
    finally:
        monkeypatch.delenv("DISCOVERY_SCAN_ABSENT_THRESHOLD", raising=False)
        get_discovery_settings.cache_clear()


def test_incomplete_scan_does_not_count_absence(db_session):
    source = make_source(db_session, max_listings=1)
    # Page of exactly `budget` jobs with more remaining => complete=False.
    full = stub_fetcher({"https://boards-api.greenhouse.io/": gh_payload(
        [gh_job(1, "Backend Engineer", "https://boards.greenhouse.io/acme/jobs/1")], total=5,
    )})
    run = service.run_scan(db_session, USER_ID, source.id, fetcher=full)
    assert run.status == "succeeded"
    listing = listings(db_session)[0]

    # Different single job, still truncated => job 1 unseen but scan incomplete.
    other = stub_fetcher({"https://boards-api.greenhouse.io/": gh_payload(
        [gh_job(2, "Frontend Engineer", "https://boards.greenhouse.io/acme/jobs/2")], total=5,
    )})
    run = service.run_scan(db_session, USER_ID, source.id, fetcher=other)
    assert run.status == "succeeded"
    db_session.refresh(listing)
    assert listing.status == "active"
    assert listing.absent_scans == 0  # incomplete scans never count absence


def test_presence_resets_absent_counter(db_session):
    source = make_source(db_session)
    payload = gh_payload([gh_job(1, "Backend Engineer", "https://boards.greenhouse.io/acme/jobs/1")])
    empty = gh_payload([])
    service.run_scan(db_session, USER_ID, source.id,
                     fetcher=stub_fetcher({"https://boards-api.greenhouse.io/": payload}))
    listing = listings(db_session)[0]
    service.run_scan(db_session, USER_ID, source.id,
                     fetcher=stub_fetcher({"https://boards-api.greenhouse.io/": empty}))
    db_session.refresh(listing)
    assert listing.absent_scans == 1
    service.run_scan(db_session, USER_ID, source.id,
                     fetcher=stub_fetcher({"https://boards-api.greenhouse.io/": payload}))
    db_session.refresh(listing)
    assert listing.absent_scans == 0
    assert listing.status == "active"


def test_reopen_on_reappearance(db_session, monkeypatch):
    monkeypatch.setenv("DISCOVERY_SCAN_ABSENT_THRESHOLD", "1")
    from app.discovery.config import get_discovery_settings

    get_discovery_settings.cache_clear()
    try:
        source = make_source(db_session)
        payload = gh_payload([gh_job(1, "Backend Engineer", "https://boards.greenhouse.io/acme/jobs/1")])
        empty = gh_payload([])
        service.run_scan(db_session, USER_ID, source.id,
                         fetcher=stub_fetcher({"https://boards-api.greenhouse.io/": payload}))
        listing = listings(db_session)[0]
        service.run_scan(db_session, USER_ID, source.id,
                         fetcher=stub_fetcher({"https://boards-api.greenhouse.io/": empty}))
        db_session.refresh(listing)
        assert listing.status == "closed"

        service.run_scan(db_session, USER_ID, source.id,
                         fetcher=stub_fetcher({"https://boards-api.greenhouse.io/": payload}))
        db_session.refresh(listing)
        assert listing.status == "active"
        assert listing.closed_at is None
        assert listing.closed_reason is None
        assert listing.absent_scans == 0
        # history preserved: still exactly one listing row, same id
        assert len(listings(db_session)) == 1
    finally:
        monkeypatch.delenv("DISCOVERY_SCAN_ABSENT_THRESHOLD", raising=False)
        get_discovery_settings.cache_clear()


def test_foreign_source_scan_raises_lookup(db_session):
    other = make_source(db_session, owner_id=OTHER_USER_ID)
    with pytest.raises(LookupError):
        service.run_scan(db_session, USER_ID, other.id, fetcher=stub_fetcher({}))


def test_active_scan_conflicts(db_session):
    source = make_source(db_session)
    db_session.add(DiscoveryRun(
        source_id=source.id, owner_id=USER_ID, status="running", trigger="manual",
        started_at=service.utcnow(),
    ))
    db_session.commit()
    with pytest.raises(service.SourceScanConflict):
        service.run_scan(db_session, USER_ID, source.id, fetcher=stub_fetcher({}))


def test_weird_titles_do_not_break_hashing(db_session):
    source = make_source(db_session, adapter="company_careers",
                         config={"url": "https://acme.example/careers", "company_name": "Acme"})
    weird = 'Backend "Engineer" \n\nSr. — café ☕'
    run = service.run_scan(db_session, USER_ID, source.id, fetcher=stub_fetcher({
        "https://acme.example/careers": careers_html(weird, "https://acme.example/careers/1", "Acme"),
    }))
    assert run.status == "succeeded"
    assert run.created_count == 1


def test_due_sources_selection(db_session):
    source = make_source(db_session, enabled=False)
    assert service.due_sources(db_session) == []
    source = service.update_source(db_session, source, enabled=True)
    # next_run_at is in the future right after enable; force it due.
    source.next_run_at = service.utcnow() - timedelta(seconds=1)
    db_session.commit()
    due = service.due_sources(db_session)
    assert [s.id for s in due] == [source.id]


# ------------------------------------------------------------------ scheduler

def test_scheduler_disabled_by_default(db_session):
    scheduler = DiscoveryScheduler(session_factory=lambda: db_session)
    import asyncio

    asyncio.run(scheduler.start())
    assert scheduler.running is False


def test_scheduler_tick_scans_due_sources(db_session, monkeypatch):
    import os

    from app.core.config import get_settings

    get_settings.cache_clear()
    source = make_source(db_session, config={
        "board_token": "acme", "url": "https://boards.greenhouse.io/acme",
    })
    source.next_run_at = service.utcnow() - timedelta(seconds=1)
    db_session.commit()
    monkeypatch.setattr(
        service, "default_fetcher",
        lambda: stub_fetcher({"https://boards-api.greenhouse.io/": gh_payload([
            gh_job(1, "Backend Engineer", "https://boards.greenhouse.io/acme/jobs/1"),
        ])}),
    )
    # A real session factory: tick() opens and closes its own session.
    eng = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    Factory = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    scheduler = DiscoveryScheduler(session_factory=Factory)
    assert scheduler.tick() == 1

    with Factory() as db:
        fresh = db.get(DiscoverySource, source.id)
        assert fresh.last_success_at is not None
        run = db.execute(
            select(DiscoveryRun).where(DiscoveryRun.source_id == source.id)
        ).scalars().one()
        assert run.status == "succeeded"
        assert run.trigger == "scheduled"


# ----------------------------------------------------------------------- API

def test_api_source_crud_and_owner_scoping(client, auth_headers):
    r = client.post("/api/discovery/sources", headers=auth_headers, json={
        "name": "Acme GH", "adapter": "greenhouse", "config": {"board_token": "acme"},
    })
    assert r.status_code == 201, r.text
    source = r.json()
    assert source["adapter"] == "greenhouse"
    assert source["next_run_at"] is not None

    r = client.get("/api/discovery/sources", headers=auth_headers)
    assert r.status_code == 200
    assert [s["id"] for s in r.json()] == [source["id"]]

    r = client.patch(f"/api/discovery/sources/{source['id']}", headers=auth_headers,
                     json={"interval_minutes": 30, "enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    assert r.json()["next_run_at"] is None

    # second user cannot see it
    r2 = client.post("/api/auth/register", json={"username": "other", "password": "password123"})
    other_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    assert client.get("/api/discovery/sources", headers=other_headers).json() == []
    assert client.get(f"/api/discovery/sources/{source['id']}", headers=other_headers).status_code == 404
    assert client.patch(f"/api/discovery/sources/{source['id']}", headers=other_headers,
                        json={"enabled": True}).status_code == 404


def test_api_invalid_source_config_is_400(client, auth_headers):
    r = client.post("/api/discovery/sources", headers=auth_headers, json={
        "name": "bad", "adapter": "greenhouse", "config": {"board_token": "no spaces!"},
    })
    assert r.status_code == 400


def test_api_manual_run_and_listing_visibility(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        service, "default_fetcher",
        lambda: stub_fetcher({"https://boards-api.greenhouse.io/": gh_payload([
            gh_job(1, "Backend Engineer", "https://boards.greenhouse.io/acme/jobs/1"),
        ])}),
    )
    r = client.post("/api/discovery/sources", headers=auth_headers, json={
        "name": "Acme", "adapter": "greenhouse", "config": {"board_token": "acme"},
    })
    source_id = r.json()["id"]

    r = client.post("/api/discovery/runs", headers=auth_headers, json={"source_id": source_id})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "succeeded"
    assert run["created_count"] == 1

    r = client.get("/api/discovery/listings", headers=auth_headers)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["status"] == "active"
    assert len(rows[0]["sources"]) == 1

    r = client.get(f"/api/discovery/listings/{rows[0]['id']}", headers=auth_headers)
    assert r.status_code == 200

    # unknown source -> 404, not a scan of someone else's source
    r = client.post("/api/discovery/runs", headers=auth_headers,
                    json={"source_id": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 404


def test_api_run_conflict_409(client, auth_headers):
    r = client.post("/api/discovery/sources", headers=auth_headers, json={
        "name": "Acme", "adapter": "greenhouse", "config": {"board_token": "acme"},
    })
    source_id = r.json()["id"]

    import os

    from app.core.config import get_settings

    get_settings.cache_clear()
    eng = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=eng)
    from app.db import models

    with Session() as db:
        user = db.execute(select(models.User)).scalars().first()
        db.add(DiscoveryRun(
            source_id=source_id, owner_id=user.id, status="running", trigger="manual",
            started_at=datetime.now(timezone.utc),
        ))
        db.commit()

    r = client.post("/api/discovery/runs", headers=auth_headers, json={"source_id": source_id})
    assert r.status_code == 409


def test_api_listing_status_filter(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        service, "default_fetcher",
        lambda: stub_fetcher({"https://boards-api.greenhouse.io/": gh_payload([
            gh_job(1, "Backend Engineer", "https://boards.greenhouse.io/acme/jobs/1"),
        ])}),
    )
    r = client.post("/api/discovery/sources", headers=auth_headers, json={
        "name": "Acme", "adapter": "greenhouse", "config": {"board_token": "acme"},
    })
    source_id = r.json()["id"]
    client.post("/api/discovery/runs", headers=auth_headers, json={"source_id": source_id})
    active = client.get("/api/discovery/listings", headers=auth_headers, params={"status": "active"}).json()
    closed = client.get("/api/discovery/listings", headers=auth_headers, params={"status": "closed"}).json()
    assert len(active) == 1
    assert closed == []
    review = client.get("/api/discovery/listings", headers=auth_headers, params={"needs_review": True}).json()
    assert review == []
