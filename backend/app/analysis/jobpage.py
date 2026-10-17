"""Job-posting extraction from a URL: HTML -> structured JD fields.

- SSRF guard: http(s) only, blocks private/loopback/link-local targets.
- Prefers schema.org JobPosting JSON-LD; falls back to title/h1/meta heuristics.
- Never invents: every field is either extracted or None/empty.
"""

import html
import json
import re

from app.analysis.keywords import analyze_jd
from app.ingestion.jd_parser import clean_text
from app.ingestion.safe_fetch import (
    FetchPolicy,
    SafeFetchError,
    safe_fetch,
    resolve_public_host,
    validate_http_url,
)

_FETCH_TIMEOUT_S = 15.0
_MAX_BYTES = 1_000_000

_ROLE_RULES: list[tuple[str, list[str]]] = [
    ("AI Engineer", ["ai engineer", "llm", "rag", "genai", "generative ai", "prompt"]),
    ("ML Engineer", ["ml engineer", "machine learning", "mlops", "pytorch", "tensorflow"]),
    ("Backend Engineer", ["backend", "fastapi", "django", "microservice", "postgres", "api "]),
    ("Frontend Engineer", ["frontend", "react", "vue", "angular", "typescript", "css"]),
    ("Data Engineer", ["data engineer", "etl", "spark", "airflow", "warehouse"]),
    ("DevOps Engineer", ["devops", "kubernetes", "terraform", "ci/cd", "sre"]),
    ("QA Engineer", ["qa engineer", "testing", "selenium", "playwright", "test automation"]),
    ("Software Engineer", ["software engineer", "developer", "programmer"]),
]


def validate_job_url(url: str) -> str:
    """Return normalized URL (or raise ValueError). Fail-fast checks:
    scheme/port/credentials plus DNS resolution to public addresses. The
    safe fetcher re-validates at connect time and on every redirect hop."""
    from urllib.parse import urlparse

    from app.core.config import get_settings

    url = (url or "").strip()
    try:
        validated = validate_http_url(url, allowed_ports=get_settings().fetch_allowed_port_set)
        resolve_public_host(urlparse(validated).hostname or "")
    except SafeFetchError as e:
        raise ValueError(str(e)) from e
    return validated


def _strip_html(raw: str) -> str:
    no_script = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", no_script)
    return html.unescape(text)


def _meta(html_text: str, name: str) -> str:
    m = re.search(
        r'<meta[^>]+(?:name|property)=["\']' + re.escape(name) + r'["\'][^>]+content=["\']([^"\']+)',
        html_text, re.I,
    )
    return (m.group(1).strip() if m else "")


def _json_ld_job(html_text: str) -> dict:
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text, re.S | re.I,
    ):
        try:
            data = json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            types = item.get("@type", [])
            types = [types] if isinstance(types, str) else types
            if "JobPosting" not in types:
                continue
            org = item.get("hiringOrganization", {})
            org_name = org.get("name", "") if isinstance(org, dict) else ""
            desc = item.get("description", "")
            return {
                "title": str(item.get("title", ""))[:300],
                "company": str(org_name)[:300],
                "description": _strip_html(str(desc)),
                "qualifications": str(item.get("qualifications", ""))[:2000],
                "experience": str(item.get("experienceRequirements", ""))[:1000],
            }
    return {}


def categorize_role(title: str, description: str) -> str:
    blob = f"{title or ''}\n{description or ''}".lower()
    for role, markers in _ROLE_RULES:
        if any(m in blob for m in markers):
            return role
    return "Other"


def extract_job_posting(html_text: str, url: str) -> dict:
    """Parse raw HTML into JD fields. Missing pieces stay empty — never guessed."""
    ld = _json_ld_job(html_text)
    title = ld.get("title") or ""
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.S | re.I)
        title = _strip_html(m.group(1)).strip()[:300] if m else ""
    if not title:
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.S | re.I)
        title = _strip_html(m.group(1)).strip()[:300] if m else ""
    company = ld.get("company") or _meta(html_text, "og:site_name")
    description = ld.get("description") or ""
    if not description.strip():
        body = _strip_html(html_text)
        description = clean_text(body, max_chars=50_000).text
    else:
        description = clean_text(description, max_chars=50_000).text
    qualifications = ld.get("qualifications") or ""
    experience = ld.get("experience") or ""
    meta_desc = _meta(html_text, "description") or _meta(html_text, "og:description")
    return {
        "title": title,
        "company": company,
        "description": description,
        "qualifications": qualifications,
        "experience": experience,
        "meta_description": meta_desc[:1000],
        "role_category": categorize_role(title, description),
        "source_url": url,
    }


def _fetch_page(url: str, timeout_s: float, max_bytes: int) -> tuple[str, dict[str, str]]:
    """Fetch page text through the single safe fetcher.

    Module-level so tests can monkeypatch the whole network layer; production
    behavior: SSRF guards on every hop, connect-time destination validation,
    streamed byte cap, sanitized errors (SafeFetchError is a RuntimeError).
    """
    from app.core.config import get_settings

    s = get_settings()
    result = safe_fetch(
        url,
        policy=FetchPolicy(
            timeout_s=timeout_s,
            max_bytes=max_bytes,
            max_redirects=s.fetch_max_redirects,
            allowed_ports=s.fetch_allowed_port_set,
            user_agent=s.fetch_user_agent,
        ),
    )
    return result.content.decode("utf-8", errors="replace"), result.headers


def analyze_job_url(url: str) -> dict:
    """Fetch + extract + analyze a job posting URL. Raises ValueError/RuntimeError."""
    url = validate_job_url(url)
    try:
        html_text, headers = _fetch_page(url, _FETCH_TIMEOUT_S, _MAX_BYTES)
    except SafeFetchError as e:
        raise RuntimeError(f"failed to fetch job URL: {e}") from e
    content_type = (headers.get("content-type") or "").split(";")[0].strip().lower()
    if content_type and "html" not in content_type and "text" not in content_type:
        raise ValueError(f"URL did not return a web page (content-type: {content_type or 'unknown'})")
    posting = extract_job_posting(html_text[:_MAX_BYTES], url)
    if not posting["description"].strip():
        raise ValueError("no readable job description found on that page")
    analysis = analyze_jd(posting["description"])
    return {"posting": posting, "analysis": analysis}
