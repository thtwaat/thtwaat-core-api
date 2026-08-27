"""Router-level tests for /api/v2/studio/static-sites — real HTTP requests
through FastAPI's TestClient, service layer mocked out (mirrors
tests/unit/command_center/test_ceo_analysis.py's dependency-override style)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from datetime import datetime, timezone

from app.auth.router import get_current_user
from app.static_sites.router import get_static_site_service, router
from app.static_sites.schemas import StaticSiteDeploymentResponse


def _fake_deployment_response(**overrides) -> StaticSiteDeploymentResponse:
    base = dict(
        id=uuid4(), site_id=uuid4(), version=1, is_current=True, provider="static",
        status="completed", stage="completed", source_type="html", environment="production",
        live=True, file_count=1, total_bytes=10, duration_ms=5, retryable=False,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return StaticSiteDeploymentResponse(**base)


def _profile(role: str = "admin"):
    return SimpleNamespace(
        id=str(uuid4()), email="user@example.com", role=role, company_id=str(uuid4()),
    )


@pytest.fixture
def app(tmp_path, monkeypatch):
    # Never let upload-endpoint tests write into the real repo's
    # data/static-sites/ — isolate to a throwaway directory.
    monkeypatch.setattr("app.static_sites.router.settings.STATIC_SITES_DIR", str(tmp_path / "static-sites"))
    fastapi_app = FastAPI()
    fastapi_app.include_router(router)
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.mark.unit
def test_upload_requires_authentication(app):
    def _deny():
        raise HTTPException(status_code=401, detail="Not authenticated")

    app.dependency_overrides[get_current_user] = _deny
    client = TestClient(app)
    resp = client.post(
        f"/api/v2/studio/static-sites/{uuid4()}/upload",
        files={"file": ("index.html", b"<html></html>", "text/html")},
    )
    assert resp.status_code == 401


@pytest.mark.unit
def test_upload_rejects_unsupported_extension(app):
    app.dependency_overrides[get_current_user] = lambda: _profile()
    fake_service = MagicMock()
    app.dependency_overrides[get_static_site_service] = lambda: fake_service
    client = TestClient(app)

    resp = client.post(
        f"/api/v2/studio/static-sites/{uuid4()}/upload",
        files={"file": ("malware.exe", b"MZ...", "application/octet-stream")},
    )

    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]
    fake_service.deploy_upload.assert_not_called()


@pytest.mark.unit
def test_upload_rejects_oversized_html(app, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: _profile()
    fake_service = MagicMock()
    app.dependency_overrides[get_static_site_service] = lambda: fake_service
    monkeypatch.setattr("app.static_sites.router.settings.STATIC_SITE_MAX_FILE_BYTES", 10)
    client = TestClient(app)

    resp = client.post(
        f"/api/v2/studio/static-sites/{uuid4()}/upload",
        files={"file": ("index.html", b"<html>" * 100, "text/html")},
    )

    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"]
    fake_service.deploy_upload.assert_not_called()


@pytest.mark.unit
def test_upload_rejects_empty_file(app):
    app.dependency_overrides[get_current_user] = lambda: _profile()
    fake_service = MagicMock()
    app.dependency_overrides[get_static_site_service] = lambda: fake_service
    client = TestClient(app)

    resp = client.post(
        f"/api/v2/studio/static-sites/{uuid4()}/upload",
        files={"file": ("index.html", b"", "text/html")},
    )

    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


@pytest.mark.unit
def test_upload_html_success_calls_service_with_correct_source_type(app):
    app.dependency_overrides[get_current_user] = lambda: _profile()
    fake_service = MagicMock()
    fake_service.deploy_upload.return_value = _fake_deployment_response()
    app.dependency_overrides[get_static_site_service] = lambda: fake_service
    client = TestClient(app)

    resp = client.post(
        f"/api/v2/studio/static-sites/{uuid4()}/upload",
        files={"file": ("index.html", b"<html>hi</html>", "text/html")},
        data={"domain_mode": "free_subdomain"},
    )

    assert resp.status_code == 201
    _, kwargs = fake_service.deploy_upload.call_args
    assert kwargs["source_type"] == "html"
    assert kwargs["original_filename"] == "index.html"
    assert kwargs["upload_size_bytes"] == len(b"<html>hi</html>")
    # Cleanup of upload_path is the (real) service's job in its `finally`
    # block — deploy_upload is mocked here, so just confirm the router wrote
    # the streamed bytes to a server-generated temp path, not a client name.
    assert kwargs["upload_path"].name != "index.html"
    assert kwargs["upload_path"].exists()
    assert kwargs["upload_path"].read_bytes() == b"<html>hi</html>"


@pytest.mark.unit
def test_upload_zip_success_calls_service_with_correct_source_type(app):
    app.dependency_overrides[get_current_user] = lambda: _profile()
    fake_service = MagicMock()
    fake_service.deploy_upload.return_value = _fake_deployment_response()
    app.dependency_overrides[get_static_site_service] = lambda: fake_service
    client = TestClient(app)

    resp = client.post(
        f"/api/v2/studio/static-sites/{uuid4()}/upload",
        files={"file": ("site.zip", b"PK\x03\x04fakezipbytes", "application/zip")},
    )

    assert resp.status_code == 201
    _, kwargs = fake_service.deploy_upload.call_args
    assert kwargs["source_type"] == "zip"


@pytest.mark.unit
def test_cross_company_site_returns_404_through_router(app):
    app.dependency_overrides[get_current_user] = lambda: _profile()
    fake_service = MagicMock()
    fake_service.get_site.side_effect = HTTPException(status_code=404, detail="Static site not found")
    app.dependency_overrides[get_static_site_service] = lambda: fake_service
    client = TestClient(app)

    resp = client.get(f"/api/v2/studio/static-sites/{uuid4()}")

    assert resp.status_code == 404


@pytest.mark.unit
def test_rollback_forbidden_for_non_manager_role_propagates(app):
    app.dependency_overrides[get_current_user] = lambda: _profile("employee")
    fake_service = MagicMock()
    fake_service.rollback.side_effect = HTTPException(
        status_code=403, detail="Only company owners and admins can deploy or rollback"
    )
    app.dependency_overrides[get_static_site_service] = lambda: fake_service
    client = TestClient(app)

    resp = client.post(f"/api/v2/studio/static-sites/{uuid4()}/rollback")

    assert resp.status_code == 403
