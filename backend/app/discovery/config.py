"""Discovery-specific settings (env: DISCOVERY_*).

Kept out of app.core.config so concurrent feature work does not contend on
one file; same BaseSettings/.env conventions apply.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class DiscoverySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    #: In-process scheduler loop (off by default; enable in deployments).
    discovery_scheduler_enabled: bool = False
    #: Seconds between "is anything due?" ticks.
    discovery_scheduler_interval_s: float = 30.0
    #: Successful *complete* scans a listing must be absent from before it
    #: is closed. A failed or truncated scan never counts.
    discovery_scan_absent_threshold: int = 3
    #: Per-fetch byte/timeout caps for discovery scans.
    discovery_fetch_timeout_s: float = 20.0
    discovery_fetch_max_bytes: int = 2_000_000
    discovery_fetch_max_redirects: int = 5


@lru_cache(maxsize=1)
def get_discovery_settings() -> DiscoverySettings:
    return DiscoverySettings()
