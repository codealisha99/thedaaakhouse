"""Company research — fetch real pages, extract (never invent).

Returns extracted title/meta/sentences + technology signals found in page text,
each claim joined to its source. If nothing fetchable is provided, says so
instead of fabricating a profile.
"""

import re
from datetime import datetime, timezone

from app.analysis.keywords import TECH_LEXICON, tokenize
from app.ingestion.web_loader import fetch_url_text

_TAG_RE = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.S)
_WS_RE = re.compile(r"\s+")


def _visible_text(html: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html or "")).strip()


def research_company(name: str, website: str | None = None) -> dict:
    if not website:
        return {
            "name": name,
            "website": None,
            "profile": {},
            "sources": [],
            "note": "No company URL provided — paste the company website to run real research. Nothing was fabricated.",
        }
    doc = fetch_url_text(website)
    text = _visible_text(doc.text)
    title = (re.search(r"<title>(.*?)</title>", doc.text, re.S | re.I) or [None, ""])[1].strip()[:200]
    meta = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', doc.text, re.I)
    description = (meta.group(1).strip()[:500] if meta else "")

    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if 40 < len(s.strip()) < 400]
    key_sents = [s for s in sents if re.search(
        r"\b(we|our|platform|product|engineer|build|ai|data|cloud|api|open source|mission)\b", s, re.I
    )][:5]
    signals = sorted({t for t in tokenize(text) if t in TECH_LEXICON})[:15]
    now = datetime.now(timezone.utc).isoformat()

    return {
        "name": name,
        "website": website,
        "profile": {
            "page_title": title,
            "description": description,
            "extracted_statements": key_sents,
            "technology_signals": signals,
        },
        "sources": [{"source_url": website, "source_title": title, "retrieved_at": now}],
        "note": "Extracted verbatim from the fetched page. Interpret, don't over-claim.",
    }
