"""Unit + integration coverage for Monitoring & Admin Operations."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.monitoring.models import AlertSeverity, AlertStatus, DeploymentAction
from app.monitoring.queue import JOBS_KEY, DEAD_KEY
from app.monitoring.schemas import (
    AlertCreateRequest,
    CancelJobRequest,
    EnqueueJobRequest,
    RetryJobRequest,
)
from app.monitoring.service import MonitoringOpsService
from app.monitoring import queue as queue_mod


# Helper used only if we export fingerprint — service uses private method.
def _fp(source, metric, title):
    return MonitoringOpsService(MagicMock())._fingerprint(source, metric, title)


def test_fingerprint_stable():
    a = _fp("queue", "queue_depth", "Job queue depth elevated")
    b = _fp("queue", "queue_depth", "Job queue depth elevated")
    assert a == b
    assert len(a) == 32


def test_alert_create_schema():
    body = AlertCreateRequest(
        severity=AlertSeverity.CRITICAL,
        title="DB down",
        body="Database health check failed",
        notify_push=True,
    )
    assert body.severity == AlertSeverity.CRITICAL
    with pytest.raises(ValidationError):
        AlertCreateRequest(title="", body="x")


def test_job_request_bounds():
    assert RetryJobRequest(index=0, dead=True).dead is True
    assert CancelJobRequest(index=2, dead=False).index == 2
    assert EnqueueJobRequest(type="backup.full").type == "backup.full"
    with pytest.raises(ValidationError):
        EnqueueJobRequest(type="")


def test_observability_links_use_settings(monkeypatch):
    svc = MonitoringOpsService(MagicMock())
    monkeypatch.setattr(
        "app.monitoring.service.metrics_mod.snapshot",
        lambda db=None: {
            "api_requests": 100,
            "errors": 5,
            "queue_depth": 3,
            "messages_total": 10,
            "messages_per_min": 1.0,
            "uptime_seconds": 60,
        },
    )
    monkeypatch.setattr(
        "app.monitoring.service.queue_mod.cache_hit_ratio",
        lambda: {"ok": True, "hit_ratio": 0.91},
    )
    monkeypatch.setattr(
        "app.monitoring.service.health_mod.check_database",
        lambda db: {"ok": True, "latency_ms": 1.2},
    )
    monkeypatch.setattr("app.monitoring.service.settings.GRAFANA_URL", "http://grafana.test")
    monkeypatch.setattr("app.monitoring.service.settings.PROMETHEUS_URL", "http://prom.test")

    obs = svc.observability()
    assert obs.grafana_url == "http://grafana.test"
    assert obs.prometheus_url == "http://prom.test"
    assert obs.metrics_endpoint == "/metrics"
    assert obs.error_rates["in_process_error_rate"] == 0.05
    assert obs.cache_hit_ratio == 0.91
    assert obs.queue_depth == 3


def test_platform_overview_counts(monkeypatch):
    db = MagicMock()
    # scalar called many times — return increasing ints
    values = [10, 4, 20, 8, 5, 12, 7, 1000, 200, 3, 50, 20]
    db.scalar = MagicMock(side_effect=values)
    svc = MonitoringOpsService(db)
    monkeypatch.setattr(
        "app.monitoring.service.queue_mod.queue_stats",
        lambda: {"ok": True, "queue_depth": 1},
    )
    monkeypatch.setattr(
        "app.monitoring.service.metrics_mod.certificates_expiring",
        lambda db: {"expiring_30d": 0, "expired": 0},
    )
    overview = svc.platform_overview()
    assert overview.active_users == 10
    assert overview.companies == 4
    assert overview.agents == 20
    assert overview.published_agents == 8
    assert overview.billing_summary["revenue_paid"] == 1000.0
    assert overview.onboarding["completion_rate"] == 40.0


def test_list_alerts_aggregates(monkeypatch):
    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.count.return_value = 2
    q.order_by.return_value.limit.return_value.all.return_value = []
    db.scalar = MagicMock(side_effect=[1, 3, 9])
    svc = MonitoringOpsService(db)
    result = svc.list_alerts()
    assert result.total == 2
    assert result.critical_open == 1
    assert result.warning_open == 3
    assert result.resolved == 9


def test_acknowledge_resolves_flow():
    db = MagicMock()
    alert = SimpleNamespace(
        id=uuid.uuid4(),
        status=AlertStatus.OPEN,
        details={},
        acknowledged_by=None,
        acknowledged_at=None,
        resolved_by=None,
        resolved_at=None,
        severity=AlertSeverity.WARNING,
        title="t",
        body="b",
        source="s",
        metric=None,
        fingerprint="fp",
        notified_channels=[],
        company_id=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.get.return_value = alert
    svc = MonitoringOpsService(db)
    svc._record_activity = MagicMock()  # type: ignore[method-assign]

    from app.monitoring.schemas import AlertAckRequest, AlertResolveRequest

    ack = svc.acknowledge_alert(alert.id, uuid.uuid4(), AlertAckRequest(note="looking"))
    assert alert.status == AlertStatus.ACKNOWLEDGED
    assert ack.status == AlertStatus.ACKNOWLEDGED

    resolved = svc.resolve_alert(alert.id, uuid.uuid4(), AlertResolveRequest(note="fixed"))
    assert alert.status == AlertStatus.RESOLVED
    assert resolved.status == AlertStatus.RESOLVED


def test_queue_constants():
    assert JOBS_KEY == "thtwaat:jobs"
    assert DEAD_KEY == "thtwaat:jobs:dead"


def test_cancel_job_records_history(monkeypatch):
    svc = MonitoringOpsService(MagicMock())
    monkeypatch.setattr(
        queue_mod,
        "cancel_job",
        lambda index, dead=False, job_id=None: {"cancelled": True, "payload": {"type": "x"}},
    )
    svc._record_deployment = MagicMock()  # type: ignore[method-assign]
    svc._record_activity = MagicMock()  # type: ignore[method-assign]
    svc.db.commit = MagicMock()
    out = svc.cancel_job(uuid.uuid4(), CancelJobRequest(index=0, dead=False))
    assert out["cancelled"] is True
    assert svc._record_deployment.called
    assert svc._record_activity.called


@pytest.mark.integration
def test_monitoring_routes_require_auth(client):
    assert client.get("/api/v1/admin/overview").status_code in (401, 403)
    assert client.get("/api/v1/monitoring/health").status_code in (401, 403)
    assert client.get("/api/v1/operations/jobs").status_code in (401, 403)
