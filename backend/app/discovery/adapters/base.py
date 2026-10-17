"""Adapter contract for discovery sources (spec §3)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ObservedJob:
    """One job as published by a source, pre-normalization."""

    title: str
    source_url: str
    external_id: str | None = None
    company_name: str | None = None
    location: str | None = None
    remote_mode: str | None = None
    employment_type: str | None = None
    description: str | None = None
    apply_url: str | None = None
    posted_at: datetime | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class AdapterResult:
    jobs: list[ObservedJob]
    #: Opaque adapter cursor to pass to the next scan (None = no more).
    cursor: dict | None
    #: True only when the source was enumerated to exhaustion within budget.
    complete: bool
    diagnostics: dict = field(default_factory=dict)


class AdapterError(RuntimeError):
    """Scan failure with a sanitized, user-safe message and stable code.

    A failed fetch/parse must never be reported as an empty successful scan.
    """

    def __init__(self, message: str, code: str, internal: str | None = None):
        super().__init__(message)
        self.code = code
        self.internal = internal or message


class SourceConfigError(AdapterError):
    def __init__(self, message: str, internal: str | None = None):
        super().__init__(message, code="invalid_config", internal=internal)


#: Fetch seam: URL -> object with status_code/url/headers/content (bytes).
#: Live runs use app.ingestion.safe_fetch.safe_fetch; tests inject stubs.
Fetcher = Callable[[str], object]


class BaseAdapter(ABC):
    name: str = ""

    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher

    @abstractmethod
    def discover(self, config: dict, cursor: dict | None, budget: int) -> AdapterResult:
        """Fetch and parse up to `budget` jobs. Raises AdapterError on any
        failure (HTTP, parse, config) — never returns success for them."""

    @staticmethod
    def validate_config(config: dict) -> dict:
        """Validate/normalize stored config. Raises SourceConfigError."""
        raise NotImplementedError
