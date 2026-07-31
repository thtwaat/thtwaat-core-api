"""Access control for the Prometheus /metrics endpoint.

The instrumentator exposes raw request/latency series that leak route names,
traffic volume and error rates. In hardened environments (production/staging)
the endpoint is restricted to internal scrapers or callers that present
``METRICS_TOKEN``; development keeps it open so local dashboards keep working.
"""
from __future__ import annotations

import hmac
import ipaddress
import logging
from typing import List, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config.settings import settings

logger = logging.getLogger(__name__)

METRICS_PATH = "/metrics"

# Headers nginx (or any reverse proxy) adds. Their presence means the request
# arrived from the public edge rather than the internal scrape network, so the
# socket-level peer address cannot be trusted for authorization.
_PROXY_HEADERS = ("x-forwarded-for", "x-forwarded-host", "x-real-ip", "forwarded")


def _parse_networks(raw: List[str]) -> List[ipaddress._BaseNetwork]:
    networks = []
    for entry in raw or []:
        try:
            networks.append(ipaddress.ip_network(entry.strip(), strict=False))
        except ValueError:
            logger.warning("[Metrics] Ignoring invalid METRICS_ALLOWED_NETWORKS entry: %r", entry)
    return networks


def _token_matches(request: Request, expected: str) -> bool:
    provided: Optional[str] = request.headers.get("x-metrics-token")
    if not provided:
        auth = request.headers.get("authorization", "")
        scheme, _, credentials = auth.partition(" ")
        if scheme.lower() == "bearer":
            provided = credentials.strip()
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)


class MetricsAccessMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._networks = _parse_networks(settings.METRICS_ALLOWED_NETWORKS)

    def _is_internal(self, request: Request) -> bool:
        if any(header in request.headers for header in _PROXY_HEADERS):
            return False
        client = request.client
        if client is None:
            return False
        try:
            peer = ipaddress.ip_address(client.host)
        except ValueError:
            return False
        return any(peer in network for network in self._networks)

    async def dispatch(self, request: Request, call_next):
        if request.url.path.rstrip("/") != METRICS_PATH:
            return await call_next(request)

        if not settings.METRICS_ENABLED:
            return JSONResponse({"detail": "Not Found"}, status_code=404)

        if not settings.is_hardened_env:
            return await call_next(request)

        token = (settings.METRICS_TOKEN or "").strip()
        if token and _token_matches(request, token):
            return await call_next(request)

        if self._is_internal(request):
            return await call_next(request)

        logger.warning(
            "[Metrics] Blocked unauthorized /metrics request from %s",
            request.client.host if request.client else "unknown",
        )
        return JSONResponse({"detail": "Not Found"}, status_code=404)
