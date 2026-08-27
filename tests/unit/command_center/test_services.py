"""Unit tests for Command Center service (no Docker)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.command_center.schemas import DashboardResponse
from app.command_center.services import CommandCenterService


@pytest.mark.unit
def test_conversion_rate_zero_when_no_customers():
    db = MagicMock()
    svc = CommandCenterService(db)
    assert svc._conversion_rate(0) == 0.0


@pytest.mark.unit
def test_conversion_rate_paid_share():
    db = MagicMock()
    db.query.return_value.filter.return_value.scalar.return_value = 2
    svc = CommandCenterService(db)
    assert svc._conversion_rate(4) == 50.0


@pytest.mark.unit
def test_get_dashboard_metrics_uses_real_helpers(monkeypatch):
    db = MagicMock()
    svc = CommandCenterService(db)
    monkeypatch.setattr(svc, "_billing_kpis", lambda: {"revenue": 10.0, "mrr": 5.0})
    monkeypatch.setattr(svc, "_active_customers", lambda: 3)
    monkeypatch.setattr(svc, "_active_projects", lambda: 2)
    monkeypatch.setattr(svc, "_leads_count", lambda: 1)
    monkeypatch.setattr(svc, "_conversion_rate", lambda n: 33.33)
    monkeypatch.setattr(svc, "_ai_tasks", lambda: 9)
    monkeypatch.setattr(svc, "_human_escalations", lambda: 4)
    monkeypatch.setattr(svc, "_ai_cost", lambda: 1.5)

    result = svc.get_dashboard_metrics()
    assert result.revenue == 10.0
    assert result.mrr == 5.0
    assert result.customers == 3
    assert result.active_projects == 2
    assert result.leads == 1
    assert result.conversion == 33.33
    assert result.ai_tasks == 9
    assert result.human_escalations == 4
    assert result.ai_cost == 1.5


@pytest.mark.unit
def test_normalize_three_pads_and_truncates():
    assert len(CommandCenterService._normalize_three(["a"])) == 3
    assert CommandCenterService._normalize_three(["a", "b", "c", "d"]) == ["a", "b", "c"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_analyze_ceo_uses_factory_not_aiservice(monkeypatch):
    db = MagicMock()
    svc = CommandCenterService(db)
    metrics = DashboardResponse(
        revenue=10.0,
        mrr=5.0,
        customers=3,
        active_projects=2,
        leads=1,
        conversion=33.33,
        ai_tasks=9,
        human_escalations=4,
        ai_cost=1.5,
    )
    monkeypatch.setattr(svc, "get_dashboard_metrics", lambda: metrics)

    payload = {
        "business_status": "OK",
        "problems": ["P1"],
        "opportunities": ["O1"],
        "you_must_decide": ["D1", "D2", "D3"],
        "recommendations": ["R1"],
    }
    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock(
        return_value=MagicMock(content=json.dumps(payload), model_used="gpt-4o-mini")
    )
    monkeypatch.setattr(
        "app.command_center.services.AIProviderFactory.get_provider",
        lambda name: mock_provider,
    )

    result = await svc.analyze_ceo()
    assert result.business_status == "OK"
    assert result.you_must_decide == ["D1", "D2", "D3"]
    assert result.metrics_snapshot.customers == 3
    mock_provider.generate.assert_awaited_once()
