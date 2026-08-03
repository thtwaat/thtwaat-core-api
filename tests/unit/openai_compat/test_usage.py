"""Unit tests — usage tracking for openai_compat (Week 2 Day 5)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.openai_compat.dependencies import CompletionsPrincipal
from app.openai_compat.usage import estimate_completion_cost, record_completion_usage, usage_analytics_payload


@pytest.mark.unit
def test_estimate_completion_cost_uses_resolver_pricing():
    cost = estimate_completion_cost(
        provider="openai",
        model="gpt-4o-mini",
        prompt_tokens=1000,
        completion_tokens=1000,
        company_id=uuid.uuid4(),
    )
    # openai defaults: 0.005 + 0.015 per 1k = 0.02
    assert cost == pytest.approx(0.02)


@pytest.mark.unit
def test_estimate_stub_provider_is_zero():
    cost = estimate_completion_cost(
        provider="stub",
        model="thtwaat-stub-mini",
        prompt_tokens=100,
        completion_tokens=100,
        company_id=uuid.uuid4(),
    )
    assert cost == 0.0


@pytest.mark.unit
def test_record_completion_usage_calls_usage_service():
    db = MagicMock()
    principal = CompletionsPrincipal(
        company_id=uuid.uuid4(),
        api_key_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
    )
    with patch("app.usage.service.UsageService") as svc_cls:
        instance = svc_cls.return_value
        db.query.return_value.filter.return_value.first.return_value = None
        summary = record_completion_usage(
            db,
            principal,
            provider="openai",
            model="gpt-4o-mini",
            prompt_tokens=10,
            completion_tokens=5,
            completion_id="chatcmpl_x",
        )
    instance.record_ai_usage.assert_called_once()
    kwargs = instance.record_ai_usage.call_args.kwargs
    assert kwargs["prompt_tokens"] == 10
    assert kwargs["completion_tokens"] == 5
    assert kwargs["source"] == "openai_compat"
    assert summary["recorded"] is True
    assert summary["total_tokens"] == 15
    assert summary["estimated_cost"] > 0


@pytest.mark.unit
def test_usage_analytics_payload_shape():
    db = MagicMock()
    company_id = uuid.uuid4()
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    end = datetime(2026, 8, 31, 23, 59, 59, tzinfo=timezone.utc)

    current = MagicMock(
        plan="starter",
        period_type="monthly",
        period_start=start,
        period_end=end,
        usage=MagicMock(
            ai_messages=3,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            api_requests=3,
        ),
        limits=MagicMock(max_messages=5000, max_tokens=1_000_000),
        progress=[MagicMock(dimension="ai_messages", current=3, limit=5000, percent=0.06)],
        upgrade_url="/billing",
    )
    history = MagicMock(points=[])

    with patch("app.usage.service.UsageService") as svc_cls:
        svc = svc_cls.return_value
        svc.current_usage.return_value = current
        svc.history.return_value = history
        payload = usage_analytics_payload(db, company_id)

    assert payload["object"] == "thtwaat.usage"
    assert payload["plan"] == "starter"
    assert payload["monthly"]["total_tokens"] == 30
    assert payload["billing"]["upgrade_url"] == "/billing"
    assert payload["company_id"] == str(company_id)
