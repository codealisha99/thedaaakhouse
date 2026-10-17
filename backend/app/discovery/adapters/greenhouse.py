"""Greenhouse job board adapter.

API: GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
with start/count pagination. Verified against the public Greenhouse API
docs; job IDs are stable per board and reusable across scans.
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
from app.discovery.normalize import detect_remote_mode, html_to_text, parse_posted_at

_TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")
_PAGE_SIZE = 50  # Greenhouse's documented per-request max


def _token_from_url(url: str) -> str | None:
    """boards.greenhouse.io/{token} or boards.eu.greenhouse.io/{token}."""
    try:
        parts = urlparse(url)
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if host not in ("boards.greenhouse.io", "boards.eu.greenhouse.io", "job-boards.greenhouse.io"):
        return None
    token = parts.path.strip("/").split("/")[0] if parts.path.strip("/") else ""
    return token or None


class GreenhouseAdapter(BaseAdapter):
    name = "greenhouse"

    @staticmethod
    def validate_config(config: dict) -> dict:
        if not isinstance(config, dict):
            raise SourceConfigError("config must be an object")
        token = (config.get("board_token") or "").strip()
        url = (config.get("url") or "").strip()
        if not token and url:
            token = _token_from_url(url) or ""
        if not token or not _TOKEN_RE.match(token):
            raise SourceConfigError(
                "greenhouse config needs a valid board_token, or url of the "
                "form https://boards.greenhouse.io/{board_token}"
            )
        return {
            "board_token": token,
            "url": url or f"https://boards.greenhouse.io/{token}",
            "company_name": (config.get("company_name") or "").strip() or None,
            "domain": (config.get("domain") or "").strip().lower() or None,
        }

    def discover(self, config: dict, cursor: dict | None, budget: int) -> AdapterResult:
        cfg = self.validate_config(config)
        token = cfg["board_token"]
        offset = int((cursor or {}).get("offset") or 0)
        if offset < 0:
            offset = 0
        company_default = cfg.get("company_name") or token

        jobs: list[ObservedJob] = []
        pages = 0
        total: int | None = None
        complete = False
        while len(jobs) < budget:
            take = min(_PAGE_SIZE, budget - len(jobs))
            url = (
                f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
                f"?content=true&start={offset}&count={take}"
            )
            payload = self._get_json(url)
            batch = payload.get("jobs") or []
            if not isinstance(batch, list):
                raise AdapterError("greenhouse response has no jobs list", code="invalid_response")
            meta = payload.get("meta") or {}
            if isinstance(meta.get("total"), int):
                total = meta["total"]
            pages += 1
            for raw in batch:
                if not isinstance(raw, dict):
                    continue
                jobs.append(self._map_job(raw, company_default))
            offset += len(batch)
            if len(batch) < take:
                complete = True  # short page => board exhausted
                break
            if total is not None and offset >= total:
                complete = True
                break
        else:
            # Budget exhausted exactly at a page boundary; unknown if more exist.
            complete = total is not None and offset >= total

        return AdapterResult(
            jobs=jobs,
            cursor={"offset": offset} if not complete else None,
            complete=complete,
            diagnostics={"pages": pages, "total": total, "fetched": len(jobs)},
        )

    def _get_json(self, url: str) -> dict:
        try:
            result = self.fetcher(url)
        except Exception as e:  # SafeFetchError and friends — sanitized upstream
            code = getattr(e, "code", "fetch_failed")
            raise AdapterError(
                "greenhouse board fetch failed (unreachable, blocked, or too large)",
                code="source_unavailable" if code in ("fetch_failed", "unresolvable_host") else "blocked_url",
                internal=str(e),
            ) from e
        try:
            data = json.loads(bytes(result.content).decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            raise AdapterError(
                "greenhouse response was not valid JSON", code="invalid_response", internal=str(e)
            ) from e
        if not isinstance(data, dict):
            raise AdapterError("greenhouse response was not a JSON object", code="invalid_response")
        return data

    @staticmethod
    def _map_job(raw: dict, company_default: str) -> ObservedJob:
        title = (raw.get("title") or "").strip()
        absolute_url = (raw.get("absolute_url") or "").strip()
        if not title or not absolute_url:
            raise AdapterError(
                "greenhouse job missing title or absolute_url", code="invalid_response"
            )
        location = ((raw.get("location") or {}).get("name") or "").strip() or None
        content_html = raw.get("content") or ""
        description = html_to_text(content_html) if isinstance(content_html, str) else None
        return ObservedJob(
            title=title,
            source_url=absolute_url,
            external_id=str(raw["id"]) if raw.get("id") is not None else None,
            company_name=(raw.get("company_name") or "").strip() or company_default,
            location=location,
            remote_mode=detect_remote_mode(location, content_html if isinstance(content_html, str) else ""),
            employment_type=None,  # not published on this endpoint
            description=description,
            apply_url=absolute_url,
            posted_at=None,  # updated_at is not a posting date — left null per spec
            extra={"greenhouse_updated_at": raw.get("updated_at")},
        )
