"""Adapter registry."""

from __future__ import annotations

from app.discovery.adapters.base import (
    AdapterError,
    AdapterResult,
    BaseAdapter,
    Fetcher,
    ObservedJob,
    SourceConfigError,
)
from app.discovery.adapters.company_careers import CompanyCareersAdapter
from app.discovery.adapters.greenhouse import GreenhouseAdapter
from app.discovery.adapters.lever import LeverAdapter

ADAPTERS: dict[str, type[BaseAdapter]] = {
    GreenhouseAdapter.name: GreenhouseAdapter,
    LeverAdapter.name: LeverAdapter,
    CompanyCareersAdapter.name: CompanyCareersAdapter,
}


def get_adapter_class(name: str) -> type[BaseAdapter]:
    try:
        return ADAPTERS[name]
    except KeyError:
        raise SourceConfigError(
            f"unknown adapter '{name}' (available: {', '.join(sorted(ADAPTERS))})"
        ) from None


__all__ = [
    "ADAPTERS",
    "AdapterError",
    "AdapterResult",
    "BaseAdapter",
    "Fetcher",
    "ObservedJob",
    "SourceConfigError",
    "get_adapter_class",
]
