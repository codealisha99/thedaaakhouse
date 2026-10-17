"""Web loader: fetch a URL -> markdown/text.

Goes through the single safe fetcher (app.ingestion.safe_fetch): SSRF guards,
connect-time destination validation, bounded redirects and streamed bytes.
Timeouts + size caps; fetched text is untrusted input and is never executed.
"""

from app.ingestion.safe_fetch import DEFAULT_MAX_BYTES, FetchPolicy, safe_fetch
from app.ingestion.jd_parser import ParsedDocument, clean_text


def fetch_url_text(url: str, timeout_s: float = 20.0, max_chars: int = 50_000,
                   max_bytes: int = DEFAULT_MAX_BYTES) -> ParsedDocument:
    """Fetch URL text through the safe fetcher.

    Raises ValueError/SafeFetchError (a RuntimeError subclass) for invalid or
    blocked URLs and failed/oversized fetches — same callable failure contract
    as before, now applied to every hop and to the connected destination.
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
    return clean_text(result.content.decode("utf-8", errors="replace"), max_chars=max_chars)
