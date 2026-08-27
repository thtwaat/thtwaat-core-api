"""Unit tests: Command Center AI CEO route — mocked LLM, no Docker/Redis."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.router import get_current_user
from app.command_center.router import get_command_center_service, router
from app.command_center.schemas import CeoAnalysisResponse, DashboardResponse
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission


def _profile(role: str):
    return SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        email="admin@example.com",
        role=role,
        company_id="00000000-0000-0000-0000-000000000002",
    )


@pytest.fixture
def ceo_app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    yield app
    app.dependency_overrides.clear()


@pytest.mark.unit
def test_ceo_analysis_unauthorized_without_user(ceo_app):
    """No auth override → missing credentials path via get_current_user dependency."""

    def _deny():
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Not authenticated")

    ceo_app.dependency_overrides[get_current_user] = _deny
    client = TestClient(ceo_app)
    resp = client.post("/api/v1/command-center/ceo-analysis")
    assert resp.status_code == 401


@pytest.mark.unit
def test_ceo_analysis_employee_forbidden(ceo_app):
    ceo_app.dependency_overrides[get_current_user] = lambda: _profile("employee")
    client = TestClient(ceo_app)
    resp = client.post("/api/v1/command-center/ceo-analysis")
    assert resp.status_code == 403


@pytest.mark.unit
def test_ceo_analysis_company_owner_forbidden(ceo_app):
    ceo_app.dependency_overrides[get_current_user] = lambda: _profile("company_owner")
    client = TestClient(ceo_app)
    resp = client.post("/api/v1/command-center/ceo-analysis")
    assert resp.status_code == 403


@pytest.mark.unit
def test_ceo_analysis_super_admin_success_mocked(ceo_app):
    metrics = DashboardResponse(
        revenue=10.0,
        mrr=5.0,
        customers=3,
        active_projects=2,
        leads=1,
        conversion=33.3,
        ai_tasks=9,
        human_escalations=4,
        ai_cost=1.5,
    )
    analysis = CeoAnalysisResponse(
        generated_at=datetime.now(timezone.utc),
        metrics_snapshot=metrics,
        business_status="Stable",
        problems=["P1"],
        opportunities=["O1"],
        you_must_decide=["D1", "D2", "D3"],
        recommendations=["R1"],
        provider="openai",
        model_used="gpt-4o-mini",
    )

    svc = MagicMock()
    svc.analyze_ceo = AsyncMock(return_value=analysis)

    ceo_app.dependency_overrides[get_current_user] = lambda: _profile("super_admin")
    ceo_app.dependency_overrides[get_command_center_service] = lambda: svc

    client = TestClient(ceo_app)
    resp = client.post("/api/v1/command-center/ceo-analysis")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["business_status"] == "Stable"
    assert data["you_must_decide"] == ["D1", "D2", "D3"]
    assert data["metrics_snapshot"]["customers"] == 3
    assert data["provider"] == "openai"
    svc.analyze_ceo.assert_awaited_once()


@pytest.mark.unit
def test_platform_admin_permission_required_for_ceo():
    """Guardrail: PLATFORM_ADMIN is required (Super Admin only)."""
    RequirePermission(Permission.PLATFORM_ADMIN)("super_admin")
    with pytest.raises(Exception) as exc:
        RequirePermission(Permission.PLATFORM_ADMIN)("employee")
    assert getattr(exc.value, "status_code", None) == 403
