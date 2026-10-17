"""In-process asyncio scheduler for due discovery sources.

Disabled by default (`DISCOVERY_SCHEDULER_ENABLED=false`); when enabled the
lifespan hook starts one loop that scans due sources inline on a worker
thread. The durable task API (step 02 follow-ups) supersedes this loop once
task execution lands — the loop is intentionally thin over `run_scan`.
"""

from __future__ import annotations

import asyncio

from app.core.logging import get_logger

from app.discovery.config import get_discovery_settings
from app.discovery.service import SourceScanConflict, run_scan

log = get_logger(__name__)


class DiscoveryScheduler:
    def __init__(self, session_factory=None, interval_s: float | None = None):
        self._session_factory = session_factory
        s = get_discovery_settings()
        self._interval_s = interval_s if interval_s is not None else s.discovery_scheduler_interval_s
        self._task: asyncio.Task | None = None
        self._stopping: asyncio.Event | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if not get_discovery_settings().discovery_scheduler_enabled:
            log.info("discovery scheduler disabled (DISCOVERY_SCHEDULER_ENABLED=false)")
            return
        if self.running:
            return
        self._stopping = asyncio.Event()
        self._task = asyncio.create_task(self._loop(), name="discovery-scheduler")
        log.info("discovery scheduler started (interval=%.1fs)", self._interval_s)

    async def stop(self) -> None:
        if self._stopping is not None:
            self._stopping.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(self._task), timeout=10)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
            self._task = None
        self._stopping = None

    async def _loop(self) -> None:
        assert self._stopping is not None
        while not self._stopping.is_set():
            try:
                await asyncio.to_thread(self.tick)
            except Exception:  # noqa: BLE001 — the loop must survive any tick failure
                log.exception("discovery scheduler tick failed")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval_s)
            except asyncio.TimeoutError:
                pass

    def tick(self) -> int:
        """Scan due sources once; returns how many scans were started."""
        from app.discovery.service import due_sources

        if self._session_factory is None:
            from app.db.database import SessionLocal

            factory = SessionLocal
        else:
            factory = self._session_factory
        started = 0
        with factory() as db:
            for source in due_sources(db):
                try:
                    run_scan(db, source.owner_id, source.id, trigger="scheduled")
                    started += 1
                except SourceScanConflict:
                    continue
                except LookupError:
                    continue
                except Exception:  # noqa: BLE001 — one bad source must not stall the rest
                    log.exception("scheduled scan failed for source %s", source.id)
        return started
