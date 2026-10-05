"""Web loader: fetch a URL -> markdown/text. Used by JD-URL ingest and (later)
company research. Timeouts + size caps; never executes fetched content."""

import httpx

from app.ingestion.jd_parser import ParsedDocument, clean_text


def fetch_url_text(url: str, timeout_s: float = 20.0, max_chars: int = 50_000) -> ParsedDocument:
    try:
        r = httpx.get(url, timeout=timeout_s, follow_redirects=True, headers={"User-Agent": "thedaaakhouse/0.1"})
        r.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"failed to fetch URL: {e}") from e
    return clean_text(r.text, max_chars=max_chars)
