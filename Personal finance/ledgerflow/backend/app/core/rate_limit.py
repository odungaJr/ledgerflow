"""
Per-IP rate limiting for auth endpoints.

Plain in-memory sliding window — no new dependency, fine for the current
single-process deployment (see docker-compose.yml: one `backend` container).
If the app is ever scaled to multiple backend replicas this needs a shared
store (e.g. Redis) instead, since each process would otherwise keep its own
counters.

Client identification: prefers the leftmost `X-Forwarded-For` entry over
`request.client.host`. Safe to trust here because the backend is never
reachable directly — docker-compose.yml only `expose`s it, Caddy is the sole
published entry point (port 80) and always sets this header on proxied
requests, so an external caller can't reach the backend to forge it.
"""
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

_WINDOW_SECONDS = 60
_buckets: dict[str, deque] = defaultdict(deque)
_lock = Lock()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(max_requests: int):
    """FastAPI dependency factory: at most `max_requests` per client IP per
    rolling minute, scoped per-route (each decorated endpoint gets its own
    buckets, keyed by path + IP)."""

    def _dependency(request: Request):
        key = f"{request.url.path}:{_client_ip(request)}"
        now = time.monotonic()
        with _lock:
            bucket = _buckets[key]
            while bucket and now - bucket[0] > _WINDOW_SECONDS:
                bucket.popleft()
            if len(bucket) >= max_requests:
                raise HTTPException(status_code=429, detail="Too many requests — try again shortly")
            bucket.append(now)

    return _dependency


def reset_rate_limits() -> None:
    """Test-only helper: clear all rate-limit state between tests, since the
    buckets live on this module for the whole test process, not per-request."""
    with _lock:
        _buckets.clear()
