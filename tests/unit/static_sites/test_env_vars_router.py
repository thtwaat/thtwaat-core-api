"""Router-level tests for /api/v2/studio/static-sites/{site_id}/env-vars —
real HTTP requests through FastAPI's TestClient, service layer mocked out
(mirrors tests/unit/static_sites/test_router.py's dependency-override
style)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.auth.router import get_current_user
from app.static_sites.router import get_env_var_service, router
from app.static_sites.schemas import StaticSiteEnvVarListResponse, StaticSiteEnvVarResponse

SECRET_PLAINTEXT = "SUPER_SECRET_123456"


def _fake_env_var_response(**overrides) -> StaticSiteEnvVarResponse:
    base = dict(
        id=uuid4(), site_id=uuid4(), key="OPENAI_API_KEY", environment="production",
        is_secret=True, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return StaticSiteEnvVarResponse(**base)


def _profile(role: str = "admin"):
    return SimpleNamespace(id=str(uuid4()), email="user@example.com", role=role, company_id=str(uuid4()))


@pytest.fixture
def app():
    fastapi_app = FastAPI()
    fastapi_app.include_router(router)
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.mark.unit
def test_list_requires_authentication(app):
    def _deny():
        raise HTTPException(status_code=401, detail="Not authenticated")

    app.dependency_overrides[get_current_user] = _deny
    client = TestClient(app)
    resp = client.get(f"/api/v2/studio/static-sites/{uuid4()}/env-vars")
    assert resp.status_code == 401


@pytest.mark.unit
def test_create_env_var_success():
    app_ = FastAPI()
    app_.include_router(router)
    app_.dependency_overrides[get_current_user] = lambda: _profile("admin")
    fake_service = MagicMock()
    fake_service.create_env_var.return_value = _fake_env_var_response()
    app_.dependency_overrides[get_env_var_service] = lambda: fake_service
    client = TestClient(app_)

    resp = client.post(
        f"/api/v2/studio/static-sites/{uuid4()}/env-vars",
        json={"key": "OPENAI_API_KEY", "value": SECRET_PLAINTEXT, "environment": "production", "is_secret": True},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["key"] == "OPENAI_API_KEY"
    assert "value" not in body
    assert "encrypted_value" not in body
    assert SECRET_PLAINTEXT not in resp.text


@pytest.mark.unit
def test_create_env_var_invalid_key_returns_422():
    app_ = FastAPI()
    app_.include_router(router)
    app_.dependency_overrides[get_current_user] = lambda: _profile("admin")
    fake_service = MagicMock()
    app_.dependency_overrides[get_env_var_service] = lambda: fake_service
    client = TestClient(app_)

    resp = client.post(
        f"/api/v2/studio/static-sites/{uuid4()}/env-vars",
        json={"key": "FOO-BAR", "value": "x", "environment": "production"},
    )
    assert resp.status_code == 422
    fake_service.create_env_var.assert_not_called()


@pytest.mark.unit
def test_create_env_var_invalid_environment_returns_422():
    app_ = FastAPI()
    app_.include_router(router)
    app_.dependency_overrides[get_current_user] = lambda: _profile("admin")
    fake_service = MagicMock()
    app_.dependency_overrides[get_env_var_service] = lambda: fake_service
    client = TestClient(app_)

    # "staging" (not "preview" — THTWAAT Deploy Phase 6A made "preview" a
    # valid environment, see app/static_sites/schemas.py) is still rejected.
    resp = client.post(
        f"/api/v2/studio/static-sites/{uuid4()}/env-vars",
        json={"key": "FOO", "value": "x", "environment": "staging"},
    )
    assert resp.status_code == 422


@pytest.mark.unit
def test_create_env_var_forbidden_for_non_manager_role_propagates():
    app_ = FastAPI()
    app_.include_router(router)
    app_.dependency_overrides[get_current_user] = lambda: _profile("employee")
    fake_service = MagicMock()
    fake_service.create_env_var.side_effect = HTTPException(
        status_code=403, detail="Only company owners and admins can manage environment variables"
    )
    app_.dependency_overrides[get_env_var_service] = lambda: fake_service
    client = TestClient(app_)

    resp = client.post(
        f"/api/v2/studio/static-sites/{uuid4()}/env-vars",
        json={"key": "FOO", "value": "bar", "environment": "production"},
    )
    assert resp.status_code == 403


@pytest.mark.unit
def test_list_env_vars_success():
    app_ = FastAPI()
    app_.include_router(router)
    app_.dependency_overrides[get_current_user] = lambda: _profile("admin")
    fake_service = MagicMock()
    fake_service.list_env_vars.return_value = StaticSiteEnvVarListResponse(
        items=[_fake_env_var_response(), _fake_env_var_response(key="DATABASE_URL")], total=2
    )
    app_.dependency_overrides[get_env_var_service] = lambda: fake_service
    client = TestClient(app_)

    resp = client.get(f"/api/v2/studio/static-sites/{uuid4()}/env-vars")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    for item in body["items"]:
        assert "value" not in item
        assert "encrypted_value" not in item


@pytest.mark.unit
def test_get_env_var_cross_company_returns_404():
    app_ = FastAPI()
    app_.include_router(router)
    app_.dependency_overrides[get_current_user] = lambda: _profile("admin")
    fake_service = MagicMock()
    fake_service.get_env_var.side_effect = HTTPException(status_code=404, detail="Environment variable not found")
    app_.dependency_overrides[get_env_var_service] = lambda: fake_service
    client = TestClient(app_)

    resp = client.get(f"/api/v2/studio/static-sites/{uuid4()}/env-vars/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.unit
def test_update_env_var_success():
    app_ = FastAPI()
    app_.include_router(router)
    app_.dependency_overrides[get_current_user] = lambda: _profile("admin")
    fake_service = MagicMock()
    fake_service.update_env_var.return_value = _fake_env_var_response(is_secret=False)
    app_.dependency_overrides[get_env_var_service] = lambda: fake_service
    client = TestClient(app_)

    resp = client.patch(
        f"/api/v2/studio/static-sites/{uuid4()}/env-vars/{uuid4()}",
        json={"value": "new-value", "is_secret": False},
    )
    assert resp.status_code == 200
    assert "value" not in resp.json()


@pytest.mark.unit
def test_delete_env_var_success_returns_204():
    app_ = FastAPI()
    app_.include_router(router)
    app_.dependency_overrides[get_current_user] = lambda: _profile("admin")
    fake_service = MagicMock()
    fake_service.delete_env_var.return_value = None
    app_.dependency_overrides[get_env_var_service] = lambda: fake_service
    client = TestClient(app_)

    resp = client.delete(f"/api/v2/studio/static-sites/{uuid4()}/env-vars/{uuid4()}")
    assert resp.status_code == 204
    assert resp.text == ""


@pytest.mark.unit
def test_delete_env_var_cross_company_returns_404():
    app_ = FastAPI()
    app_.include_router(router)
    app_.dependency_overrides[get_current_user] = lambda: _profile("admin")
    fake_service = MagicMock()
    fake_service.delete_env_var.side_effect = HTTPException(status_code=404, detail="Environment variable not found")
    app_.dependency_overrides[get_env_var_service] = lambda: fake_service
    client = TestClient(app_)

    resp = client.delete(f"/api/v2/studio/static-sites/{uuid4()}/env-vars/{uuid4()}")
    assert resp.status_code == 404
