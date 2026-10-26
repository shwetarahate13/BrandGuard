"""Small process-local rate limiter for the newly added API surfaces."""
from __future__ import annotations

import re
import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse


class EndpointRateLimiter:
    def __init__(self) -> None:
        self._rules = [
            ("POST", re.compile(r"^/api/auth/login$"), 10),
            ("POST", re.compile(r"^/api/auth/demo-login$"), 20),
            ("GET", re.compile(r"^/api/guidelines/health$"), 60),
            ("POST", re.compile(r"^/api/guidelines/recompute$"), 10),
            ("PATCH", re.compile(r"^/api/guidelines/clauses/[A-Za-z0-9-]+$"), 20),
            ("GET", re.compile(r"^/api/submissions/[A-Za-z0-9-]+/versions/[A-Za-z0-9-]+/source$"), 60),
            ("POST", re.compile(r"^/api/decisions$"), 30),
            ("POST", re.compile(r"^/api/findings/[A-Za-z0-9-]+/decision$"), 30),
            ("POST", re.compile(r"^/api/findings/[A-Za-z0-9-]+/escalate-review$"), 30),
            ("GET", re.compile(r"^/api/feedback/stats$"), 60),
            ("POST", re.compile(r"^/api/feedback/reset$"), 10),
        ]
        self._requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._operation_count = 0

    async def __call__(self, request: Request, call_next):
        matched = next(
            ((pattern.pattern, limit) for method, pattern, limit in self._rules
             if request.method == method and pattern.fullmatch(request.url.path)),
            None,
        )
        if matched is None:
            return await call_next(request)

        route_key, limit = matched
        client_key = request.client.host if request.client else "unknown"
        key = (client_key, route_key)
        now = time.monotonic()
        window_seconds = 60.0
        retry_after = None
        with self._lock:
            bucket = self._requests[key]
            while bucket and now - bucket[0] >= window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(window_seconds - (now - bucket[0])))
            else:
                bucket.append(now)
            self._operation_count += 1
            if self._operation_count % 1000 == 0:
                expired = [bucket_key for bucket_key, times in self._requests.items() if not times or now - times[-1] >= window_seconds]
                for bucket_key in expired:
                    self._requests.pop(bucket_key, None)

        if retry_after is not None:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)


endpoint_rate_limiter = EndpointRateLimiter()
