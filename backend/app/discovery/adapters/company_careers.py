"""Company careers-page adapter (bounded HTML/JSON-LD extraction).

Fetches the configured URL and extracts JobPosting records from embedded
JSON-LD (`<script type="application/ld+json">`) or a raw JSON body of the
same shape. Single-page and bounded by design: no link crawling in this
milestone (documented gap).

Safety rule: a page that yields zero JobPosting markers fails the scan
(`no_jobs_parsed`) instead of reporting an empty successful enumeration —
a template change must never look like "all jobs closed".
"""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from app.discovery.adapters.base import (
    AdapterError,
    AdapterResult,
    BaseAdapter,
    ObservedJob,
    SourceConfigError,
)
from app.discovery.normalize import (
    detect_remote_mode,
    html_to_text,
    parse_posted_at,
    validate_source_url,
)

_LD_SCRIPT_RE = re.compile(
    r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(?P<body>.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)


def _iter_jsonld(node):
    """Yield every dict in a JSON-LD tree (arrays, @graph, nesting)."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _iter_jsonld(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_jsonld(item)


def _job_location(node: dict) -> str | None:
    loc = node.get("jobLocation")
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if not isinstance(loc, dict):
        return None
    address = loc.get("address")
    if isinstance(address, list):
        address = address[0] if address else None
    if not isinstance(address, dict):
        # Some publishers put locality directly on jobLocation.
        address = loc
    parts = [
        address.get("addressLocality"),
        address.get("addressRegion"),
        address.get("addressCountry"),
    ]
    text = ", ".join(str(p).strip() for p in parts if p and str(p).strip())
    return text or None


def _hiring_org_name(node: dict, fallback: str | None) -> str | None:
    org = node.get("hiringOrganization")
    if isinstance(org, list):
        org = org[0] if org else None
    if isinstance(org, dict) and org.get("name"):
        return str(org["name"]).strip() or fallback
    return fallback


def _employment_type(node: dict) -> str | None:
    value = node.get("employmentType")
    if isinstance(value, list):
        value = value[0] if value else None
    return str(value).strip() if value else None


class CompanyCareersAdapter(BaseAdapter):
    name = "company_careers"

    @staticmethod
    def validate_config(config: dict) -> dict:
        if not isinstance(config, dict):
            raise SourceConfigError("config must be an object")
        url = (config.get("url") or "").strip()
        if not url:
            raise SourceConfigError("company_careers config needs a careers page url")
        try:
            validate_source_url(url)
        except ValueError as e:
            raise SourceConfigError(str(e)) from e
        return {
            "url": url,
            "company_name": (config.get("company_name") or "").strip() or None,
            "domain": (config.get("domain") or "").strip().lower() or None,
            "allow_empty": bool(config.get("allow_empty", False)),
        }

    def discover(self, config: dict, cursor: dict | None, budget: int) -> AdapterResult:
        cfg = self.validate_config(config)
        url = cfg["url"]
        try:
            result = self.fetcher(url)
        except Exception as e:
            code = getattr(e, "code", "fetch_failed")
            raise AdapterError(
                "careers page fetch failed (unreachable, blocked, or too large)",
                code="source_unavailable" if code in ("fetch_failed", "unresolvable_host") else "blocked_url",
                internal=str(e),
            ) from e
        try:
            body = bytes(result.content).decode("utf-8", errors="replace")
        except (AttributeError, TypeError) as e:
            raise AdapterError(
                "careers page response was empty", code="invalid_response", internal=str(e)
            ) from e

        postings, marker_found = self._extract_postings(body)
        if not postings and not marker_found and not cfg.get("allow_empty"):
            # Zero markers is a parse failure, not a legitimately empty board.
            raise AdapterError(
                "careers page contained no JobPosting structured data "
                "(page structure may have changed)",
                code="no_jobs_parsed",
            )

        offset = max(0, int((cursor or {}).get("offset") or 0))
        page = postings[offset : offset + budget]
        jobs = [self._map_job(node, cfg, url) for node in page]
        complete = offset + len(page) >= len(postings)
        return AdapterResult(
            jobs=jobs,
            cursor=None if complete else {"offset": offset + len(page)},
            complete=complete,
            diagnostics={
                "pages": 1,
                "job_postings_found": len(postings),
                "fetched": len(jobs),
                "marker_found": marker_found,
            },
        )

    @staticmethod
    def _extract_postings(body: str) -> tuple[list[dict], bool]:
        """Return (JobPosting nodes, any_marker_seen)."""
        stripped = body.lstrip()
        nodes: list[dict] = []
        marker = False
        if stripped[:1] in ("{", "["):
            # Raw JSON body (feed-style careers endpoint).
            try:
                data = json.loads(body)
            except json.JSONDecodeError as e:
                raise AdapterError(
                    "careers page looked like JSON but did not parse",
                    code="invalid_response",
                    internal=str(e),
                ) from e
            for node in _iter_jsonld(data):
                if node.get("@type") == "JobPosting":
                    marker = True
                    nodes.append(node)
            return nodes, marker
        for match in _LD_SCRIPT_RE.finditer(body):
            chunk = match.group("body").strip()
            if not chunk:
                continue
            try:
                data = json.loads(chunk)
            except json.JSONDecodeError:
                continue  # publishers ship trailing commas etc.; skip one blob
            for node in _iter_jsonld(data):
                if node.get("@type") == "JobPosting":
                    marker = True
                    nodes.append(node)
        return nodes, marker

    @staticmethod
    def _map_job(node: dict, cfg: dict, base_url: str) -> ObservedJob:
        title = html_to_text(node.get("title"))
        raw_url = (node.get("url") or node.get("@id") or "").strip()
        source_url = urljoin(base_url, raw_url) if raw_url else base_url
        if not title:
            raise AdapterError("JobPosting without a title", code="invalid_response")
        company = _hiring_org_name(node, cfg.get("company_name")) or "Unknown company"
        location = _job_location(node)
        remote_type = str(node.get("jobLocationType") or "")
        description = html_to_text(node.get("description")) or None
        return ObservedJob(
            title=title,
            source_url=source_url,
            external_id=(str(node["@id"]).strip() if node.get("@id") else None),
            company_name=company,
            location=location,
            remote_mode=detect_remote_mode(remote_type, location),
            employment_type=_employment_type(node),
            description=description,
            apply_url=source_url,
            posted_at=parse_posted_at(node.get("datePosted")),
            extra={},
        )
