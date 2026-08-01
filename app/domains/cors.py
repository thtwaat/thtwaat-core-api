"""CORS middleware — static allowlist, verified domains, and public widget paste-anywhere."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config.settings import settings

# Script-tag widget embeds call these from arbitrary customer Origins.
# Auth is the agent API key — do not widen this to /api/v1/*.
_PUBLIC_WIDGET_EXACT = frozenset({"/widget.js", "/widget.css"})


def is_public_widget_cors_path(path: str) -> bool:
    if path in _PUBLIC_WIDGET_EXACT:
        return True
    return path.startswith("/public/v1/")


def _cors_headers(allow_origin: str, request: Request) -> dict:
    req_headers = request.headers.get("access-control-request-headers", "*")
    return {
        "Access-Control-Allow-Origin": allow_origin,
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
        "Access-Control-Allow-Headers": req_headers or "*",
        "Access-Control-Expose-Headers": "*",
        "Vary": "Origin",
    }


class PublicWidgetCORSMiddleware(BaseHTTPMiddleware):
    """
    Paste-anywhere CORS for public widget assets and /public/v1/* only.

    Must be the outermost CORS-related middleware so preflights are not
    rejected by the strict SaaS CORSMiddleware allowlist.
    """

    async def dispatch(self, request: Request, call_next):
        if not is_public_widget_cors_path(request.url.path):
            return await call_next(request)

        origin = request.headers.get("origin")
        if not origin:
            return await call_next(request)

        if request.method == "OPTIONS":
            return Response(status_code=200, headers=_cors_headers(origin, request))

        response = await call_next(request)
        for key, value in _cors_headers(origin, request).items():
            response.headers[key] = value
        return response


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """
    When CORS_ORIGINS is ['*'], mirrors permissive CORS.
    Otherwise allows Origin if it is in settings.CORS_ORIGINS or a verified domain origin.
    """

    async def dispatch(self, request: Request, call_next):
        # Public widget paths are handled by PublicWidgetCORSMiddleware.
        if is_public_widget_cors_path(request.url.path):
            return await call_next(request)

        origin = request.headers.get("origin")
        static = list(settings.CORS_ORIGINS or [])
        allow_all = "*" in static

        if request.method == "OPTIONS" and origin:
            if allow_all or self._origin_allowed(origin, static, request):
                headers = _cors_headers(origin if not allow_all else "*", request)
                return Response(status_code=200, headers=headers)

        response = await call_next(request)

        if origin and (allow_all or self._origin_allowed(origin, static, request)):
            for k, v in _cors_headers(origin if not allow_all else "*", request).items():
                response.headers[k] = v
        return response

    def _origin_allowed(self, origin: str, static: list[str], request: Request) -> bool:
        if origin in static:
            return True
        try:
            from app.domains.service import get_cached_cors_origins
            from app.database.database import SessionLocal

            db = SessionLocal()
            try:
                allowed = get_cached_cors_origins(db)
            finally:
                db.close()
            return origin in allowed
        except Exception:
            return False
