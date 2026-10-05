"""In-memory sliding-window rate limiter (stdlib only, per-process).

Scope: brute-force protection on auth endpoints. Not distributed — behind
multiple workers each instance tracks its own counters (documented limit).
For Redis-backed limits, replace `allow()` internals without touching callers.
"""

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, max_hits: int, window_s: int):
        self.max_hits = max_hits
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        q = self._hits[key]
        while q and q[0] <= now - self.window_s:
            q.popleft()
        if len(q) >= self.max_hits:
            return False
        q.append(now)
        return True


auth_limiter = RateLimiter(max_hits=20, window_s=60)
