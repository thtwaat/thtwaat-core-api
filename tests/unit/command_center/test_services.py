"""Unit tests for Command Center service (no Docker)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

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
