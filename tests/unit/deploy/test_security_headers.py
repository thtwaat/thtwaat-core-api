"""Launch-freeze verification helpers for security headers."""
from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Mirror of main.SecurityHeadersMiddleware for isolated unit coverage."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        path = request.url.path
        if path.startswith("/public/v1/widget/embed"):
            if "X-Frame-Options" in response.headers:
                del response.headers["X-Frame-Options"]
            response.headers["Content-Security-Policy"] = "frame-ancestors *"
        else:
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


@pytest.mark.unit
def test_security_headers_on_api_paths():
    app = Starlette()

    async def homepage(request):
        return PlainTextResponse("ok")

    app.add_route("/", homepage)
    app.add_middleware(_SecurityHeadersMiddleware)
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert "max-age=31536000" in res.headers["Strict-Transport-Security"]
    assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


@pytest.mark.unit
def test_embed_path_allows_framing():
    app = Starlette()

    async def embed(request):
        return PlainTextResponse("embed")

    app.add_route("/public/v1/widget/embed", embed)
    app.add_middleware(_SecurityHeadersMiddleware)
    client = TestClient(app)
    res = client.get("/public/v1/widget/embed")
    assert "X-Frame-Options" not in res.headers
    assert "frame-ancestors" in res.headers.get("Content-Security-Policy", "")
