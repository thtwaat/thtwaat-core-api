"""Dynamic CORS middleware — merges static settings with verified company domains."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config.settings import settings


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """
    When CORS_ORIGINS is ['*'], mirrors permissive CORS.
    Otherwise allows Origin if it is in settings.CORS_ORIGINS or a verified domain origin.
    """

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        static = list(settings.CORS_ORIGINS or [])
        allow_all = "*" in static

        if request.method == "OPTIONS" and origin:
            if allow_all or self._origin_allowed(origin, static, request):
                headers = self._cors_headers(origin if not allow_all else "*", request)
                return Response(status_code=200, headers=headers)

        response = await call_next(request)

        if origin and (allow_all or self._origin_allowed(origin, static, request)):
            for k, v in self._cors_headers(origin if not allow_all else "*", request).items():
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

    def _cors_headers(self, allow_origin: str, request: Request) -> dict:
        req_headers = request.headers.get("access-control-request-headers", "*")
        return {
            "Access-Control-Allow-Origin": allow_origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
            "Access-Control-Allow-Headers": req_headers or "*",
            "Access-Control-Expose-Headers": "*",
            "Vary": "Origin",
        }
