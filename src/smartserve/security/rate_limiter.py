"""Rate limiting module for protecting endpoints against brute force and denial-of-service.

Implements an in-memory sliding window rate limiter suitable for local and single-node
deployments. Adheres to Docs/TASKS.md Phase 8.
"""

import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    """In-memory sliding window rate limiter per client IP or key."""

    def __init__(self, requests_per_minute: int = 60, window_sec: float = 60.0):
        self.requests_per_minute = requests_per_minute
        self.window_sec = window_sec
        self._history: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_key: str) -> tuple[bool, int]:
        """Check if request is permitted under rate limit.

        Returns (allowed, retry_after_seconds).
        """
        now = time.monotonic()
        window_start = now - self.window_sec

        # Clean old timestamps
        timestamps = [t for t in self._history[client_key] if t > window_start]
        self._history[client_key] = timestamps

        if len(timestamps) >= self.requests_per_minute:
            oldest_in_window = timestamps[0]
            retry_after = max(1, int(oldest_in_window + self.window_sec - now))
            return False, retry_after

        self._history[client_key].append(now)
        return True, 0

    def reset(self) -> None:
        """Clear recorded request timestamps."""
        self._history.clear()


def rate_limit(requests_per_minute: int = 60) -> Callable[[Request], Any]:
    """FastAPI dependency for per-client IP rate limiting."""
    limiter = SlidingWindowRateLimiter(requests_per_minute=requests_per_minute)

    async def dependency(request: Request) -> None:
        # Use client host IP or forwarded-for
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
            request.client.host if request.client else "127.0.0.1"
        )
        allowed, retry_after = limiter.is_allowed(client_ip)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
