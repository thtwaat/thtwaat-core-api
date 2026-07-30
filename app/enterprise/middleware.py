"""Enforce tenant IP, MFA, and API policies on authenticated requests."""
from __future__ import annotations

import ipaddress
import uuid
from datetime import datetime, timezone

from jose import JWTError, jwt
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.auth.model import MFASettings
from app.auth.service import ALGORITHM
from app.config.settings import settings
from app.database.database import SessionLocal
from app.enterprise.models import EnterpriseSecurityPolicy
from app.enterprise.models import AuditSeverity, EnterpriseAuditLog
from app.users.model import User


MFA_EXEMPT_PATHS = {
    "/api/v1/auth/me",
    "/api/v1/auth/logout",
    "/api/v1/auth/mfa/setup",
    "/api/v1/auth/mfa/enable",
    "/api/v1/auth/mfa/verify",
    "/api/v1/auth/mfa/backup-codes",
}


class EnterpriseSecurityMiddleware(BaseHTTPMiddleware):
    """Policy enforcement stays separate from AuthService token validation."""

    async def dispatch(self, request: Request, call_next):
        authorization = request.headers.get("authorization", "")
        if not authorization.lower().startswith("bearer "):
            return await call_next(request)
        token = authorization.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if not user_id:
                return await call_next(request)
        except JWTError:
            return await call_next(request)

        db = SessionLocal()
        try:
            user = db.get(User, uuid.UUID(str(user_id)))
            if not user:
                return await call_next(request)
            try:
                policy = db.scalar(
                    select(EnterpriseSecurityPolicy).where(
                        EnterpriseSecurityPolicy.company_id == user.company_id
                    )
                )
            except Exception:
                db.rollback()
                return await call_next(request)
            if not policy:
                return await call_next(request)

            client_ip = self._client_ip(request)
            if policy.ip_allow_list and not self._ip_allowed(client_ip, policy.ip_allow_list):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Request blocked by enterprise IP allow list"},
                )

            if policy.require_mfa and request.url.path not in MFA_EXEMPT_PATHS:
                mfa = db.scalar(
                    select(MFASettings).where(
                        MFASettings.user_id == user.id,
                        MFASettings.enabled.is_(True),
                    )
                )
                if not mfa:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": "Multi-factor authentication is required",
                            "code": "mfa_enrollment_required",
                            "setup_endpoint": "/api/v1/auth/mfa/setup",
                        },
                    )

            api_policy = dict(policy.api_policies or {})
            if api_policy.get("read_only") and request.method not in {"GET", "HEAD", "OPTIONS"}:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Tenant API policy is read-only"},
                )
            for prefix in api_policy.get("blocked_path_prefixes", []):
                if request.url.path.startswith(prefix):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Path blocked by tenant API policy"},
                    )
            max_bytes = int(api_policy.get("max_request_bytes") or 0)
            content_length = int(request.headers.get("content-length") or 0)
            if max_bytes and content_length > max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request exceeds tenant API policy size limit"},
                )
        finally:
            db.close()
        return await call_next(request)

    @staticmethod
    def _ip_allowed(client_ip: str | None, allow_list: list[str]) -> bool:
        if not client_ip:
            return False
        try:
            address = ipaddress.ip_address(client_ip)
            return any(
                address in ipaddress.ip_network(entry, strict=False)
                for entry in allow_list
            )
        except ValueError:
            return False

    @staticmethod
    def _client_ip(request: Request) -> str | None:
        direct = request.client.host if request.client else None
        if direct in set(settings.TRUSTED_PROXIES or []):
            forwarded = request.headers.get("x-forwarded-for", "")
            if forwarded:
                return forwarded.split(",", 1)[0].strip()
        return direct


class EnterpriseAuditMiddleware(BaseHTTPMiddleware):
    """Capture tenant activity for existing modules without changing their services."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if (
            request.method not in {"POST", "PUT", "PATCH", "DELETE"}
            or not request.url.path.startswith("/api/")
        ):
            return response
        authorization = request.headers.get("authorization", "")
        if not authorization.lower().startswith("bearer "):
            return response
        try:
            payload = jwt.decode(
                authorization.split(" ", 1)[1],
                settings.JWT_SECRET_KEY,
                algorithms=[ALGORITHM],
            )
            user_id = uuid.UUID(str(payload["sub"]))
        except (JWTError, KeyError, ValueError):
            return response

        db = SessionLocal()
        try:
            user = db.get(User, user_id)
            if not user:
                return response
            severity = (
                AuditSeverity.CRITICAL
                if response.status_code >= 500
                else AuditSeverity.WARNING
                if response.status_code >= 400
                else AuditSeverity.INFO
            )
            db.add(
                EnterpriseAuditLog(
                    company_id=user.company_id,
                    actor_user_id=user.id,
                    action=f"http.{request.method.lower()}",
                    resource_type="api_request",
                    resource_id=request.url.path,
                    severity=severity,
                    ip_address=EnterpriseSecurityMiddleware._client_ip(request),
                    user_agent=request.headers.get("user-agent"),
                    request_id=getattr(request.state, "request_id", None),
                    metadata_={
                        "status_code": response.status_code,
                        "query": str(request.url.query or ""),
                    },
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        return response
