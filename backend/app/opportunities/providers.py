"""Startup search providers — an injectable adapter boundary.

Step 04 only defines the contract plus a harmless default; real provider
adapters register themselves here (see docs/backend/implementation-progress.md).
A provider returns sourced leads only — it never creates opportunities on its
own, and a missing provider must not be confused with an empty result set
at the API layer (the route reports the configured provider honestly).
"""

from abc import ABC, abstractmethod

from app.core.config import get_settings


class StartupSearchProvider(ABC):
    """Search external startup directories. Leads must carry source evidence."""

    name: str = "abstract"

    @abstractmethod
    def search(self, query: str, profile: dict, limit: int) -> list[dict]:
        """Return up to `limit` leads: {name?, domain?, website, evidence[]}."""


class NullStartupSearchProvider(StartupSearchProvider):
    """Default no-network provider. Returns nothing, honestly."""

    name = "none"

    def search(self, query: str, profile: dict, limit: int) -> list[dict]:  # noqa: ARG002
        return []


_PROVIDERS: dict[str, StartupSearchProvider] = {"none": NullStartupSearchProvider()}


def register_startup_search_provider(provider: StartupSearchProvider) -> None:
    _PROVIDERS[provider.name] = provider


def available_providers() -> list[str]:
    return sorted(_PROVIDERS)


def get_startup_search_provider(name: str | None = None) -> StartupSearchProvider:
    key = name or get_settings().startup_search_provider
    provider = _PROVIDERS.get(key)
    if provider is None:
        return _PROVIDERS[NullStartupSearchProvider.name]
    return provider
