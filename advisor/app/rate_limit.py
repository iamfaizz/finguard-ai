import time
from collections import defaultdict, deque


class RateLimiter:
    """Per-user sliding window (in memory => run uvicorn with ONE worker)."""

    def __init__(self, per_minute: int) -> None:
        self._limit = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self._limit:
            return False
        q.append(now)
        return True
