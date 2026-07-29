"""Request ID + structured access logging middleware."""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("thtwaat.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            from app.deploy.metrics import incr_requests

            incr_requests()
        except Exception:
            pass

        try:
            response = await call_next(request)
        except Exception:
            try:
                from app.deploy.metrics import incr_errors

                incr_errors()
            except Exception:
                pass
            raise

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        if response.status_code >= 500:
            try:
                from app.deploy.metrics import incr_errors

                incr_errors()
            except Exception:
                pass

        logger.info(
            "request_id=%s method=%s path=%s status=%s latency_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
        )
        return response
