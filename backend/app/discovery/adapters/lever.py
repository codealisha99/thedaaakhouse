"""Lever job postings adapter.

API: GET https://api.lever.co/v0/postings/{org}?mode=json — returns the
org's full posting list in one response (verified against live Lever demo
boards). We slice it locally against the run budget using a cursor offset.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from app.discovery.adapters.base import (
    AdapterError,
    AdapterResult,
    BaseAdapter,
    ObservedJob,
    SourceConfigError,
)
from app.discovery.normalize import detect_remote_mode, parse_posted_at

_ORG_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")


def _org_from_url(url: str) -> str | None:
    """jobs.lever.co/{org} or api.lever.co/v0/postings/{org}."""
    try:
        parts = urlparse(url)
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    segments = [s for s in parts.path.split("/") if s]
    if host in ("jobs.lever.co",) and segments:
        return segments[0]
    if host == "api.lever.co" and len(segments) >= 3 and segments[:2] == ["v0", "postings"]:
        return segments[2]
    return None


class LeverAdapter(BaseAdapter):
    name = "lever"

    @staticmethod
    def validate_config(config: dict) -> dict:
        if not isinstance(config, dict):
            raise SourceConfigError("config must be an object")
        org = (config.get("org") or "").strip()
        url = (config.get("url") or "").strip()
        if not org and url:
            org = _org_from_url(url) or ""
        if not org or not _ORG_RE.match(org):
            raise SourceConfigError(
                "lever config needs a valid org slug, or url of the form "
                "https://jobs.lever.co/{org}"
            )
        return {
            "org": org,
            "url": url or f"https://jobs.lever.co/{org}",
            "company_name": (config.get("company_name") or "").strip() or None,
            "domain": (config.get("domain") or "").strip().lower() or None,
        }

    def discover(self, config: dict, cursor: dict | None, budget: int) -> AdapterResult:
        cfg = self.validate_config(config)
        org = cfg["org"]
        company_default = cfg.get("company_name") or org

        url = f"https://api.lever.co/v0/postings/{org}?mode=json"
        try:
            result = self.fetcher(url)
        except Exception as e:
            code = getattr(e, "code", "fetch_failed")
            raise AdapterError(
                "lever postings fetch failed (unreachable, blocked, or too large)",
                code="source_unavailable" if code in ("fetch_failed", "unresolvable_host") else "blocked_url",
                internal=str(e),
            ) from e
        try:
            raw_list = json.loads(bytes(result.content).decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            raise AdapterError(
                "lever response was not valid JSON", code="invalid_response", internal=str(e)
            ) from e
        if not isinstance(raw_list, list):
            # Lever returns an object like {"error": ...} for unknown orgs.
            raise AdapterError("lever response was not a postings list", code="invalid_response")

        offset = max(0, int((cursor or {}).get("offset") or 0))
        page = raw_list[offset : offset + budget]
        jobs: list[ObservedJob] = []
        for raw in page:
            if isinstance(raw, dict):
                jobs.append(self._map_job(raw, company_default))
        complete = offset + len(page) >= len(raw_list)
        return AdapterResult(
            jobs=jobs,
            cursor=None if complete else {"offset": offset + len(page)},
            complete=complete,
            diagnostics={"total": len(raw_list), "fetched": len(jobs), "pages": 1},
        )

    @staticmethod
    def _map_job(raw: dict, company_default: str) -> ObservedJob:
        title = (raw.get("text") or "").strip()
        hosted = (raw.get("hostedUrl") or "").strip()
        if not title or not hosted:
            raise AdapterError("lever posting missing text or hostedUrl", code="invalid_response")
        categories = raw.get("categories") or {}
        location = (categories.get("location") or "").strip() or None
        commitment = (categories.get("commitment") or "").strip() or None
        workplace = (raw.get("workplaceType") or "").strip() or None
        description = raw.get("descriptionPlain") or raw.get("descriptionBodyPlain") or None
        if isinstance(description, str):
            description = description.strip() or None
        return ObservedJob(
            title=title,
            source_url=hosted,
            external_id=(str(raw["id"]) if raw.get("id") else None),
            company_name=company_default,
            location=location,
            remote_mode=detect_remote_mode(workplace, location),
            employment_type=commitment,
            description=description,
            apply_url=(raw.get("applyUrl") or hosted).strip() or hosted,
            posted_at=parse_posted_at(raw.get("createdAt")),
            extra={"lever_workplace_type": workplace},
        )
