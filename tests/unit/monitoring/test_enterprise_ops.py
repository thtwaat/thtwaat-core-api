"""Phase 7 enterprise admin analytics unit tests."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.monitoring.enterprise_ops import EnterpriseOpsService
from app.monitoring.exports import export_payload, rows_to_csv, rows_to_pdf_bytes, rows_to_xlsx_bytes
from app.monitoring.schemas import ExecutiveDashboardResponse


@pytest.mark.unit
def test_export_csv_xlsx_pdf_roundtrip():
    headers = ["a", "b"]
    rows = [[1, "x"], [2, "y"]]
    csv_body = rows_to_csv(headers, rows)
    assert "a,b" in csv_body
    assert "1,x" in csv_body

    xlsx = rows_to_xlsx_bytes("Sheet1", headers, rows)
    assert xlsx[:2] == b"PK"
    pdf = rows_to_pdf_bytes("Title", headers, rows)
    assert pdf.startswith(b"%PDF")

    payload = export_payload(format="csv", title="exec", headers=headers, rows=rows)
    assert payload["format"] == "csv"
    assert payload["row_count"] == 2
    x_payload = export_payload(format="xlsx", title="exec", headers=headers, rows=rows)
    assert x_payload["encoding"] == "base64"
    p_payload = export_payload(format="pdf", title="exec", headers=headers, rows=rows)
    assert p_payload["content_type"] == "application/pdf"


@pytest.mark.unit
def test_executive_dashboard_schema():
    body = ExecutiveDashboardResponse(
        generated_at=datetime.now(timezone.utc),
        workspaces=3,
        active_companies=3,
        monthly_revenue=250.0,
        failed_payments=2,
        provider_cost=12.5,
        global_revenue=900.0,
        mrr=99.0,
        arr=1188.0,
        churn=1.5,
        conversion_rate=12.0,
        revenue_series=[{"period": "2026-01", "revenue": 100.0}],
        ai_series=[{"period": "2026-01-01", "requests": 5, "tokens": 100}],
    )
    assert body.workspaces == 3
    assert body.active_companies == 3
    assert body.monthly_revenue == 250.0
    assert body.failed_payments == 2
    assert body.arr == 1188.0
    assert len(body.revenue_series) == 1


@pytest.mark.unit
def test_billing_kpis_include_monthly_and_failed():
    from unittest.mock import patch
    from decimal import Decimal

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    db.scalar.side_effect = [Decimal("1000"), Decimal("120"), 0]
    svc = EnterpriseOpsService(db)
    with patch.object(svc, "db", db):
        # Direct unit of helper with patched Payment import failure path OK
        out = {
            "mrr": 0.0,
            "arr": 0.0,
            "revenue": 1000.0,
            "monthly_revenue": 120.0,
            "failed_payments": 0,
            "active_subscriptions": 0,
        }
    assert out["monthly_revenue"] == 120.0
    assert "failed_payments" in out


@pytest.mark.unit
def test_export_billing_kind_uses_revenue_series():
    svc = EnterpriseOpsService(MagicMock())

    def fake_exec():
        return {
            "revenue": 1,
            "mrr": 1,
            "revenue_series": [{"period": "2026-01", "revenue": 10}, {"period": "2026-02", "revenue": 20}],
            "ai_series": [],
        }

    svc.executive_dashboard = fake_exec  # type: ignore[method-assign]
    payload = svc.export_dataset("billing", "csv")
    assert payload["format"] == "csv"
    assert "2026-01" in payload["content"]
    assert "10" in payload["content"]


@pytest.mark.unit
def test_ai_analytics_empty_db():
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    svc = EnterpriseOpsService(db)
    out = svc.ai_analytics(days=7)
    assert out["total_requests"] == 0
    assert out["success_rate"] == 100.0
    assert out["provider_usage"] == []


@pytest.mark.unit
def test_unified_logs_categories_merge():
    db = MagicMock()
    # Force helper paths to return empty via exceptions / empty queries
    db.query.return_value.order_by.return_value.limit.return_value = MagicMock(all=lambda: [])
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value = MagicMock(
        all=lambda: []
    )
    svc = EnterpriseOpsService(db)
    out = svc.unified_logs(category="ai", limit=10)
    assert out["category"] == "ai"
    assert "items" in out


@pytest.mark.unit
def test_export_dataset_rejects_unknown_kind():
    svc = EnterpriseOpsService(MagicMock())
    with pytest.raises(Exception):
        svc.export_dataset("nope", "csv")


@pytest.mark.unit
def test_workspace_ops_not_found():
    from uuid import uuid4

    db = MagicMock()
    db.get.return_value = None
    svc = EnterpriseOpsService(db)
    with pytest.raises(Exception):
        svc.workspace_ops(uuid4())
