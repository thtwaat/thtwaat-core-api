"""
Intentional public (no JWT Bearer) endpoint registry.

Protected routes must declare HTTPBearer security in OpenAPI.
Anything not listed here that lacks Bearer security is treated as accidental.
"""
from __future__ import annotations

from typing import FrozenSet, Iterable, Optional, Set, Tuple

# (METHOD upper-case, OpenAPI path template) — paths match FastAPI/OpenAPI style
# (path params as {name}, trailing slashes as registered).
INTENTIONAL_PUBLIC_OPERATIONS: FrozenSet[Tuple[str, str]] = frozenset(
    {
        # Root / probes / docs (docs may be omitted in production OpenAPI)
        ("GET", "/"),
        ("GET", "/health"),
        ("GET", "/live"),
        ("GET", "/liveness"),
        ("GET", "/ready"),
        ("GET", "/readiness"),
        ("GET", "/metrics"),
        ("GET", "/docs"),
        ("GET", "/redoc"),
        ("GET", "/openapi.json"),
        # Widget static assets
        ("GET", "/widget.js"),
        ("GET", "/widget.css"),
        # System
        ("GET", "/api/v1/status"),
        # Auth bootstrap (no access JWT)
        ("POST", "/api/v1/auth/login"),
        ("POST", "/api/v1/auth/refresh"),
        ("POST", "/api/v1/auth/logout"),
        ("POST", "/api/v1/auth/send-otp"),
        ("POST", "/api/v1/auth/verify-otp"),
        ("POST", "/api/v1/auth/resend-otp"),
        ("POST", "/api/v1/auth/send-email-verification"),
        ("POST", "/api/v1/auth/verify-email"),
        ("POST", "/api/v1/auth/send-phone-verification"),
        ("POST", "/api/v1/auth/verify-phone"),
        ("POST", "/api/v1/auth/forgot-password"),
        ("POST", "/api/v1/auth/reset-password"),
        ("POST", "/api/v1/auth/mfa/verify"),
        # Signup / onboarding / invite / SSO
        ("POST", "/api/v1/companies/"),
        ("POST", "/api/v1/users/"),  # optional bearer for privileged signup
        ("GET", "/api/v1/onboarding/flow"),
        ("POST", "/api/v1/onboarding/start"),
        ("GET", "/api/v1/onboarding/resume/{resume_token}"),
        ("POST", "/api/v1/enterprise/invitations/accept"),
        ("GET", "/api/v1/enterprise/sso/{connection_id}/initiate"),
        ("POST", "/api/v1/enterprise/sso/oidc/callback"),
        # Public billing catalog
        ("GET", "/api/v1/payments/plans"),
        ("GET", "/api/v1/payments/plans/"),
        ("GET", "/api/v1/payments/plans/{plan_id}"),
        # Payment provider webhooks (signature auth)
        ("POST", "/api/v1/payments/webhooks/stripe"),
        ("POST", "/api/v1/payments/webhooks/razorpay"),
        # Public agent / branding (API key or embed token — not JWT)
        ("GET", "/public/v1/widget/embed"),
        ("GET", "/public/v1/widget/{widget_id}"),
        ("POST", "/public/v1/chat"),
        ("POST", "/public/v1/chat/stream"),
        ("POST", "/public/v1/chat/legacy"),
        ("POST", "/public/v1/leads"),
        ("POST", "/public/v1/handoff"),
        ("GET", "/public/v1/sessions/{session_id}/messages"),
        ("GET", "/public/v1/branding"),
    }
)

# OpenAPI security scheme names that satisfy "authenticated" for JWT routes.
JWT_SECURITY_SCHEME_NAMES: FrozenSet[str] = frozenset({"HTTPBearer", "Bearer"})


def normalize_path(path: str) -> str:
    """Normalize OpenAPI / route paths for allowlist comparison."""
    if not path:
        return "/"
    if not path.startswith("/"):
        path = "/" + path
    # Keep trailing slash as FastAPI registers it; collapse empty.
    return path or "/"


def operation_key(method: str, path: str) -> Tuple[str, str]:
    return (method.upper(), normalize_path(path))


def is_intentional_public(method: str, path: str) -> bool:
    return operation_key(method, path) in INTENTIONAL_PUBLIC_OPERATIONS


def _security_scheme_names(security: Optional[list]) -> Set[str]:
    names: Set[str] = set()
    if not security:
        return names
    for requirement in security:
        if isinstance(requirement, dict):
            names.update(requirement.keys())
    return names


def operation_declares_jwt_security(operation: dict, components: dict) -> bool:
    """True if the OpenAPI operation requires an HTTP Bearer JWT-style scheme."""
    security = operation.get("security")
    if security is None:
        # Inherit global security (rare in this app).
        return False
    if security == []:
        # Explicitly public in OpenAPI.
        return False
    names = _security_scheme_names(security)
    schemes = (components or {}).get("securitySchemes") or {}
    for name in names:
        if name in JWT_SECURITY_SCHEME_NAMES:
            return True
        scheme = schemes.get(name) or {}
        if scheme.get("type") == "http" and str(scheme.get("scheme", "")).lower() == "bearer":
            return True
    return False


def find_unprotected_operations(openapi: dict) -> list[Tuple[str, str]]:
    """
    Return (METHOD, path) for operations that lack Bearer security and are
    not on the intentional public allowlist.
    """
    components = openapi.get("components") or {}
    accidental: list[Tuple[str, str]] = []
    for path, path_item in (openapi.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if not isinstance(operation, dict):
                continue
            key = operation_key(method, path)
            if key in INTENTIONAL_PUBLIC_OPERATIONS:
                continue
            if operation_declares_jwt_security(operation, components):
                continue
            accidental.append(key)
    return sorted(accidental)


def find_public_ops_missing_from_allowlist(openapi: dict) -> list[Tuple[str, str]]:
    """Operations with empty/missing security that are not allowlisted (alias)."""
    return find_unprotected_operations(openapi)


def assert_allowlist_ops_exist_or_optional(
    openapi: dict,
    required: Optional[Iterable[Tuple[str, str]]] = None,
) -> list[Tuple[str, str]]:
    """
    Return allowlisted operations that are absent from the OpenAPI document.
    Docs/metrics/widget assets may be include_in_schema=False — those are OK.
    """
    skip_if_missing = frozenset(
        {
            ("GET", "/docs"),
            ("GET", "/redoc"),
            ("GET", "/openapi.json"),
            ("GET", "/metrics"),
            ("GET", "/widget.js"),
            ("GET", "/widget.css"),
            ("GET", "/liveness"),
            ("GET", "/readiness"),
            # Hidden from schema but intentionally public
            ("POST", "/public/v1/chat/legacy"),
        }
    )
    present: Set[Tuple[str, str]] = set()
    for path, path_item in (openapi.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method in path_item:
            if method.lower() in {"get", "post", "put", "patch", "delete", "head", "options"}:
                present.add(operation_key(method, path))

    check = frozenset(required) if required is not None else INTENTIONAL_PUBLIC_OPERATIONS
    missing = []
    for key in sorted(check):
        if key in skip_if_missing:
            continue
        if key not in present:
            missing.append(key)
    return missing
