from __future__ import annotations

import asyncio
import math
import time
from collections import defaultdict, deque


class InMemoryRateLimiter:
    """Sliding-window rate limiter for single-process deployments."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def retry_after_seconds(self, *, key: str, limit: int, window_seconds: int) -> int | None:
        if limit <= 0 or window_seconds <= 0:
            return None

        now = time.monotonic()
        cutoff = now - window_seconds

        async with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= limit:
                return max(1, math.ceil(hits[0] + window_seconds - now))

            hits.append(now)
            return None

    async def reset(self) -> None:
        async with self._lock:
            self._hits.clear()


chat_rate_limiter = InMemoryRateLimiter()


async def reset_rate_limiters() -> None:
    await chat_rate_limiter.reset()
