"""Regression: route auth posture + OpenAPI security definitions."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.api.router import api_router
from app.agent_platform.routers.agent_router import router as agent_router
from app.agent_platform.routers.public_router import router as public_router
from app.agent_platform.knowledge.routers import router as knowledge_router
from app.agent_platform.routers.conversation_router import router as conversation_router
from app.auth.openapi_security import AGENT_API_KEY_SCHEME, apply_openapi_security
from app.auth.public_endpoints import (
    INTENTIONAL_PUBLIC_OPERATIONS,
    assert_allowlist_ops_exist_or_optional,
    find_unprotected_operations,
    is_intentional_public,
    operation_declares_jwt_security,
)
from app.auth.service import AuthService
from app.branding.public_router import router as branding_public_router
from app.openai_compat.router import router as openai_compat_router
from app.users.model import UserStatus


def _schema_app() -> FastAPI:
    app = FastAPI(title="THTWAAT Core API", version="1.0.0")
    app.include_router(api_router)
    app.include_router(agent_router)
    app.include_router(public_router)
    app.include_router(knowledge_router)
    app.include_router(conversation_router)
    app.include_router(branding_public_router)
    app.include_router(openai_compat_router)

    @app.get("/")
    def root():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/live")
    def live():
        return {"status": "alive"}

    @app.get("/ready")
    def ready():
        return {"status": "ready"}

    return app


def _openapi() -> dict:
    app = _schema_app()
    return apply_openapi_security(app.openapi())


# ── OpenAPI security ──────────────────────────────────────────────────────────


def test_no_accidental_unprotected_openapi_operations():
    schema = _openapi()
    accidental = find_unprotected_operations(schema)
    assert accidental == [], (
        "Endpoints lack Bearer security and are not in INTENTIONAL_PUBLIC_OPERATIONS: "
        + ", ".join(f"{m} {p}" for m, p in accidental)
    )


def test_intentional_public_ops_present_in_openapi():
    schema = _openapi()
    missing = assert_allowlist_ops_exist_or_optional(schema)
    assert missing == [], (
        "Allowlisted public endpoints missing from OpenAPI: "
        + ", ".join(f"{m} {p}" for m, p in missing)
    )


def test_previously_accidental_routes_now_declare_bearer():
    schema = _openapi()
    components = schema.get("components") or {}
    must_protect = [
        ("GET", "/v2/agents/templates"),
        ("GET", "/api/v1/copilot/tools"),
        ("GET", "/api/v1/ai/providers"),
        ("GET", "/api/v1/ai/models"),
        ("GET", "/api/v1/ai/health"),
    ]
    for method, path in must_protect:
        op = schema["paths"][path][method.lower()]
        assert operation_declares_jwt_security(op, components), f"{method} {path}"
        assert not is_intentional_public(method, path)


def test_public_chat_documents_agent_api_key_scheme():
    schema = _openapi()
    schemes = schema["components"]["securitySchemes"]
    assert AGENT_API_KEY_SCHEME in schemes
    for path in ("/public/v1/chat", "/public/v1/chat/stream"):
        sec = schema["paths"][path]["post"]["security"]
        assert sec == [{AGENT_API_KEY_SCHEME: []}]


def test_status_and_login_are_explicitly_public_in_openapi():
    schema = _openapi()
    assert schema["paths"]["/api/v1/status"]["get"].get("security") == []
    assert schema["paths"]["/api/v1/auth/login"]["post"].get("security") == []
    assert ("GET", "/api/v1/status") in INTENTIONAL_PUBLIC_OPERATIONS
    assert ("POST", "/api/v1/auth/login") in INTENTIONAL_PUBLIC_OPERATIONS


# ── HTTP 401 without credentials ──────────────────────────────────────────────


PROTECTED_GETS = [
    "/api/v1/auth/me",
    "/api/v1/copilot/tools",
    "/api/v1/ai/providers",
    "/api/v1/ai/models",
    "/api/v1/ai/health",
    "/v2/agents/templates",
    "/api/v1/apps/",
    f"/api/v1/storage/{uuid.UUID(int=0)}",
]


@pytest.mark.parametrize("path", PROTECTED_GETS)
def test_protected_routes_return_401_without_bearer(path: str):
    app = _schema_app()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get(path)
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED, (
        f"{path} expected 401, got {resp.status_code}: {resp.text}"
    )


def test_intentional_public_status_ok_without_bearer():
    app = _schema_app()
    client = TestClient(app)
    resp = client.get("/api/v1/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


def test_intentional_public_plans_list_not_401():
    app = _schema_app()

    class _FakePlans:
        def list_plans(self, active_only: bool = True):
            return []

    from app.payments.plans.router import get_plan_service

    app.dependency_overrides[get_plan_service] = lambda: _FakePlans()
    client = TestClient(app)
    resp = client.get("/api/v1/payments/plans/")
    assert resp.status_code == 200
    assert resp.status_code != 401


def test_login_endpoint_accepts_unauthenticated_post():
    """Login must not require a Bearer token (422/5xx from body/deps is OK)."""
    app = _schema_app()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/auth/login", json={})
    assert resp.status_code not in (401, 403), resp.text


# ── Inactive user 401/403 consistency ─────────────────────────────────────────


def test_inactive_user_profile_returns_403_not_401():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.company_id = uuid.uuid4()
    user.email = "inactive@example.com"
    user.first_name = "In"
    user.last_name = "Active"
    user.role = MagicMock()
    user.role.value = "employee"
    user.is_active = False
    user.status = UserStatus.ACTIVE

    db = MagicMock()
    db.scalar.return_value = user
    service = AuthService(db)

    with patch("app.auth.service.jwt.decode", return_value={"sub": str(user.id), "type": "access"}):
        with pytest.raises(Exception) as exc:
            service.get_current_user_profile("token")
    assert exc.value.status_code == 403
    assert "inactive" in str(exc.value.detail).lower() or "suspended" in str(exc.value.detail).lower()


def test_missing_user_profile_returns_401():
    db = MagicMock()
    db.scalar.return_value = None
    service = AuthService(db)

    with patch("app.auth.service.jwt.decode", return_value={"sub": str(uuid.uuid4()), "type": "access"}):
        with pytest.raises(Exception) as exc:
            service.get_current_user_profile("token")
    assert exc.value.status_code == 401


def test_authenticate_inactive_user_returns_403():
    from app.auth.schema import LoginRequest

    user = MagicMock()
    user.id = uuid.uuid4()
    user.company_id = uuid.uuid4()
    user.email = "x@example.com"
    user.hashed_password = "hashed"
    user.is_active = False
    user.status = UserStatus.SUSPENDED

    db = MagicMock()
    # authenticate_user uses db.scalars(...).all() then later db.scalar for SSO/MFA
    scalars_result = MagicMock()
    scalars_result.all.return_value = [user]
    db.scalars.return_value = scalars_result
    db.scalar.return_value = None  # no SSO / no MFA

    service = AuthService(db)

    with patch.object(AuthService, "verify_password", return_value=True):
        with pytest.raises(Exception) as exc:
            service.authenticate_user(LoginRequest(email=user.email, password="pw"))
    assert exc.value.status_code == 403
