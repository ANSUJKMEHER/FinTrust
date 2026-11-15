import time
import threading
from typing import Dict, List, Optional, Tuple
from fastapi import HTTPException, Request, Response, status

from app.core.config import settings


class SlidingWindowRateLimiter:
    """Thread-safe, in-memory sliding-window rate limiter for API endpoints."""

    def __init__(self):
        self._lock = threading.Lock()
        # Mapping: key -> list of request timestamps (epoch floats)
        self._requests: Dict[str, List[float]] = {}
        self._last_cleanup = time.time()

    def _cleanup_expired(self, now: float, max_window: float = 300.0):
        """Periodically purges keys with no timestamps in the last max_window seconds."""
        if now - self._last_cleanup < 60.0:
            return
        self._last_cleanup = now
        expired_keys = []
        for key, timestamps in self._requests.items():
            valid_ts = [t for t in timestamps if now - t < max_window]
            if not valid_ts:
                expired_keys.append(key)
            else:
                self._requests[key] = valid_ts
        for k in expired_keys:
            del self._requests[k]

    def check(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> Tuple[bool, int, float]:
        """Evaluates whether a request identified by key is permitted.
        
        Returns:
            Tuple of (is_allowed, remaining_quota, retry_after_seconds)
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            self._cleanup_expired(now)

            timestamps = self._requests.get(key, [])
            # Filter timestamps within current sliding window
            timestamps = [t for t in timestamps if t > window_start]

            if len(timestamps) >= max_requests:
                # Rate limit exceeded: calculate retry-after based on oldest timestamp in window
                oldest_in_window = timestamps[0]
                retry_after = max(0.1, (oldest_in_window + window_seconds) - now)
                self._requests[key] = timestamps
                return False, 0, retry_after

            # Request is allowed: record timestamp
            timestamps.append(now)
            self._requests[key] = timestamps
            remaining = max_requests - len(timestamps)
            return True, remaining, 0.0

    def reset(self):
        """Resets all recorded rate limit state (useful in test teardown)."""
        with self._lock:
            self._requests.clear()


# Global in-memory rate limiter singleton
limiter = SlidingWindowRateLimiter()


def get_client_identifier(request: Request) -> str:
    """Extracts a reliable client identifier (IP or X-Forwarded-For) from the incoming request."""
    # Check X-Forwarded-For (from reverse proxy / load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in the comma-separated chain is the client IP
        client_ip = forwarded.split(",")[0].strip()
        if client_ip:
            return client_ip

    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"


class RateLimitDependency:
    """FastAPI route dependency that enforces rate limiting on endpoints."""

    def __init__(self, max_requests: int, window_seconds: int = 60, scope: str = "general"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.scope = scope

    async def __call__(self, request: Request, response: Response):
        if not getattr(settings, "RATE_LIMIT_ENABLED", True):
            return

        client_id = get_client_identifier(request)
        rate_key = f"{self.scope}:{client_id}"

        allowed, remaining, retry_after = limiter.check(
            key=rate_key,
            max_requests=self.max_requests,
            window_seconds=self.window_seconds
        )

        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        if not allowed:
            retry_int = int(retry_after) + 1
            response.headers["Retry-After"] = str(retry_int)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: maximum {self.max_requests} requests per {self.window_seconds}s. Retry after {retry_int} seconds.",
                headers={
                    "Retry-After": str(retry_int),
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0"
                }
            )
