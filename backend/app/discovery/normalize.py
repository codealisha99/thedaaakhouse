"""Normalization helpers for observed job data.

Pure functions, stdlib only. Conservative by design: we only strip known
tracking parameters (never meaningful job identifiers), and similarity
helpers are exposed so dedup can keep high, explainable thresholds.
"""

from __future__ import annotations

import hashlib
import html
import ipaddress
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

#: Query parameters that only decorate a link; stripped from canonical URLs.
TRACKING_PARAMS = frozenset(
    {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "gclid", "fbclid", "msclkid", "mc_cid", "mc_eid", "igshid",
        "twclid", "yclid", "_ga", "cmpid", "campaign_id",
    }
)

_ALLOWED_PORTS = frozenset({80, 443})

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_LEGAL_SUFFIX_RE = re.compile(
    r"\b(inc|llc|ltd|limited|corp|corporation|co|gmbh|pvt|pte|sarl|bv|ag|sa)\b\.?$"
)

REMOTE_HINTS = ("remote", "anywhere", "work from home", "wfh", "distributed")
HYBRID_HINTS = ("hybrid",)

_HASH_SEP = chr(31)


def validate_source_url(url: str) -> str:
    """Validate a configured source URL's *text*: scheme, credentials, port,
    and literal-IP destination. No DNS — the fetcher re-checks everything
    (including resolved addresses) at request time.

    Raises ValueError with a user-safe message.
    """
    url = (url or "").strip()
    try:
        parts = urlparse(url)
    except ValueError as e:
        raise ValueError("invalid URL") from e
    if parts.scheme not in ("http", "https"):
        raise ValueError("URL must start with http:// or https://")
    if parts.username or parts.password:
        raise ValueError("URLs with embedded credentials are not allowed")
    host = (parts.hostname or "").strip().strip("[]").lower()
    if not host:
        raise ValueError("URL has no host")
    try:
        port = parts.port
    except ValueError as e:
        raise ValueError("invalid port in URL") from e
    if port is None:
        port = 443 if parts.scheme == "https" else 80
    if port not in _ALLOWED_PORTS:
        raise ValueError(f"port {port} is not allowed (allowed: 80, 443)")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        return url  # hostname: resolved + pinned by the fetcher at request time
    folded = literal.ipv4_mapped or literal
    if not folded.is_global or folded.is_private or folded.is_loopback or folded.is_link_local:
        raise ValueError(f"refusing to use non-public address {host}")
    return url


def canonicalize_url(url: str | None) -> str | None:
    """Lowercase scheme/host, drop fragment and tracking params, drop a
    trailing slash on non-root paths. Meaningful identifiers are preserved."""
    if not url:
        return None
    url = url.strip()
    try:
        parts = urlparse(url)
    except ValueError:
        return url
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
    ]
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    netloc = parts.netloc.lower()
    return urlunparse(
        (parts.scheme.lower(), netloc, path, "", urlencode(query), "")
    )


def collapse_ws(text: str | None) -> str:
    return _WS_RE.sub(" ", (text or "")).strip()


def normalize_title(title: str | None) -> str:
    return collapse_ws(title).casefold()


def normalize_company(company: str | None) -> str:
    text = collapse_ws(company).casefold().rstrip(".")
    text = _LEGAL_SUFFIX_RE.sub("", text).strip(" ,")
    return text or collapse_ws(company).casefold()


def company_domain(url: str | None) -> str | None:
    """Registrable-ish hostname of a URL (best effort, no PSL): last two labels."""
    if not url:
        return None
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return None
    if not host:
        return None
    labels = [p for p in host.split(".") if p and p != "www"]
    if len(labels) >= 2:
        return ".".join(labels[-2:])
    return host


def detect_remote_mode(*texts: str | None) -> str:
    blob = " ".join(t for t in texts if t).casefold()
    if not blob:
        return "unknown"
    if any(h in blob for h in REMOTE_HINTS):
        return "remote"
    if any(h in blob for h in HYBRID_HINTS):
        return "hybrid"
    return "onsite"


def html_to_text(fragment: str | None) -> str:
    """Strip tags to plain text for storage/hashing (untrusted input)."""
    if not fragment:
        return ""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return collapse_ws(text)


def title_similarity(a: str | None, b: str | None) -> float:
    """SequenceMatcher ratio on normalized titles (0..1)."""
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


def locations_compatible(a: str | None, b: str | None) -> bool:
    """True when locations don't contradict: equal normalized, or one missing."""
    na, nb = collapse_ws(a).casefold(), collapse_ws(b).casefold()
    if not na or not nb:
        return True
    return na == nb


def content_hash(
    title: str | None, company: str | None, location: str | None, description: str | None
) -> str:
    parts = [
        normalize_title(title),
        normalize_company(company),
        collapse_ws(location).casefold(),
        collapse_ws(description)[:4000].casefold(),
    ]
    return hashlib.sha256(_HASH_SEP.join(parts).encode("utf-8")).hexdigest()


def parse_posted_at(value: object) -> datetime | None:
    """Greenhouse ISO-8601 strings, Lever epoch milliseconds, or datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        ms = float(value)
        if ms > 1e11:  # epoch milliseconds
            ms /= 1000.0
        try:
            dt = datetime.fromtimestamp(ms, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            return parse_posted_at(int(text))
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
