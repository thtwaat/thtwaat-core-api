"""Unit tests for THTWAAT Deploy Phase 4B secret/public-prefix protection —
a variable marked is_secret=true can never carry VITE_ or NEXT_PUBLIC_
(both are inlined into client bundles at build time). Covers both the
create-time schema validator and the update-time service-layer check (the
update payload doesn't carry the key, so that check needs the existing row)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import app.users.model  # noqa: F401
import app.apps.model  # noqa: F401
import app.companies.model  # noqa: F401
import app.auth.model  # noqa: F401
import app.storage.model  # noqa: F401
import app.domains.models  # noqa: F401
import app.static_sites.models  # noqa: F401

from app.static_sites.env_vars_service import StaticSiteEnvVarService
from app.static_sites.models import StaticSite, StaticSiteEnvironmentVariable
from app.static_sites.schemas import StaticSiteEnvVarCreateRequest, StaticSiteEnvVarUpdateRequest


def _profile(role: str = "admin", *, company_id=None):
    return SimpleNamespace(id=str(uuid4()), email="user@example.com", role=role, company_id=str(company_id or uuid4()))


# ---- create (schema-level) ---------------------------------------------------
#
# The is_secret+prefix combo is deliberately NOT rejected at the Pydantic
# schema layer (see schemas.py) — a model_validator failure makes FastAPI's
# default 422 handler echo the whole request body, `value` included, back to
# the caller. The schema lets it through; StaticSiteEnvVarService.create_env_var()
# rejects it instead (see the "create (service-level)" section below).


@pytest.mark.unit
@pytest.mark.parametrize("key", ["VITE_API_KEY", "NEXT_PUBLIC_API_KEY"])
def test_secret_with_public_prefix_accepted_by_schema_rejected_by_service_instead(key):
    req = StaticSiteEnvVarCreateRequest(key=key, value="v", environment="production", is_secret=True)
    assert req.is_secret is True  # schema itself does not reject this


@pytest.mark.unit
@pytest.mark.parametrize("key", ["VITE_API_KEY", "NEXT_PUBLIC_API_KEY"])
def test_non_secret_with_public_prefix_accepted_on_create(key):
    req = StaticSiteEnvVarCreateRequest(key=key, value="v", environment="production", is_secret=False)
    assert req.key == key


@pytest.mark.unit
def test_secret_with_server_only_key_accepted_on_create():
    req = StaticSiteEnvVarCreateRequest(key="DATABASE_URL", value="postgres://x", environment="production", is_secret=True)
    assert req.is_secret is True


# ---- create (service-level) ---------------------------------------------------


def _service() -> StaticSiteEnvVarService:
    svc = StaticSiteEnvVarService(MagicMock())
    svc.repo = MagicMock()
    return svc


def _site(workspace_id, site_id):
    return StaticSite(id=site_id, workspace_id=workspace_id, name="Acme", slug="acme")


@pytest.mark.unit
@pytest.mark.parametrize("key", ["VITE_API_KEY", "NEXT_PUBLIC_API_KEY"])
def test_create_env_var_rejects_secret_with_public_prefix(key):
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var_by_key.return_value = None

    payload = StaticSiteEnvVarCreateRequest(key=key, value="SUPER_SECRET_123456", environment="production", is_secret=True)
    with pytest.raises(HTTPException) as exc:
        svc.create_env_var(_profile("admin", company_id=company_id), site_id, payload)
    assert exc.value.status_code == 400
    assert "public prefix" in exc.value.detail
    svc.repo.create_env_var.assert_not_called()


@pytest.mark.unit
def test_create_env_var_rejection_never_echoes_the_secret_value_via_http():
    """Regression for the FastAPI-default-422-echo issue: going through the
    REAL router (not just the service) must not return the plaintext value
    anywhere in the response body."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.auth.router import get_current_user
    from app.database.database import get_db
    from app.static_sites.router import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _profile("admin")
    app.dependency_overrides[get_db] = lambda: MagicMock()
    client = TestClient(app)

    secret = "my-actual-plaintext-secret-value"
    resp = client.post(
        f"/api/v2/studio/static-sites/{uuid4()}/env-vars",
        json={"key": "VITE_SECRET", "value": secret, "environment": "production", "is_secret": True},
    )
    assert secret not in resp.text
    app.dependency_overrides.clear()


# ---- update (service-level, since key isn't in the update payload) -----------


def _env_row(*, workspace_id, site_id, key, is_secret):
    from datetime import datetime, timezone

    return StaticSiteEnvironmentVariable(
        id=uuid4(), workspace_id=workspace_id, site_id=site_id, key=key,
        encrypted_value="enc", environment="production", is_secret=is_secret,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.unit
def test_flipping_is_secret_true_on_vite_prefixed_key_rejected():
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    row = _env_row(workspace_id=company_id, site_id=site_id, key="VITE_API_KEY", is_secret=False)
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var.return_value = row

    with pytest.raises(HTTPException) as exc:
        svc.update_env_var(_profile("admin", company_id=company_id), site_id, row.id, StaticSiteEnvVarUpdateRequest(is_secret=True))
    assert exc.value.status_code == 400
    assert "public prefix" in exc.value.detail


@pytest.mark.unit
def test_flipping_is_secret_true_on_next_public_prefixed_key_rejected():
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    row = _env_row(workspace_id=company_id, site_id=site_id, key="NEXT_PUBLIC_API_KEY", is_secret=False)
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var.return_value = row

    with pytest.raises(HTTPException) as exc:
        svc.update_env_var(_profile("admin", company_id=company_id), site_id, row.id, StaticSiteEnvVarUpdateRequest(is_secret=True))
    assert exc.value.status_code == 400
    svc.repo.save_env_var.assert_not_called()


@pytest.mark.unit
def test_already_secret_public_prefixed_key_cannot_be_updated_without_clearing_secret_flag():
    """Defense in depth: even if such a row somehow already existed (e.g. a
    pre-Phase-4B row), any update that leaves is_secret=True on it is
    rejected — not just ones that explicitly set is_secret=True."""
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    row = _env_row(workspace_id=company_id, site_id=site_id, key="VITE_LEGACY_SECRET", is_secret=True)
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var.return_value = row

    with pytest.raises(HTTPException) as exc:
        svc.update_env_var(_profile("admin", company_id=company_id), site_id, row.id, StaticSiteEnvVarUpdateRequest(value="new-value"))
    assert exc.value.status_code == 400


@pytest.mark.unit
def test_updating_value_on_non_secret_public_prefixed_key_succeeds():
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    row = _env_row(workspace_id=company_id, site_id=site_id, key="VITE_API_URL", is_secret=False)
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var.return_value = row
    svc.repo.save_env_var.side_effect = lambda r: r

    resp = svc.update_env_var(_profile("admin", company_id=company_id), site_id, row.id, StaticSiteEnvVarUpdateRequest(value="https://new.example.com"))
    assert resp.key == "VITE_API_URL"
