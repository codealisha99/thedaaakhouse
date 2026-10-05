"""Ingestion: raw bytes/text/URL -> clean text. No AI here — deterministic only."""

import re
from dataclasses import dataclass


@dataclass
class ParsedDocument:
    text: str
    truncated: bool = False


def clean_text(raw: str, max_chars: int = 50_000) -> ParsedDocument:
    """Normalize whitespace; truncate defensively (LLM context limits)."""
    text = re.sub(r"\r\n?", "\n", raw or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > max_chars:
        return ParsedDocument(text=text[:max_chars], truncated=True)
    return ParsedDocument(text=text)
