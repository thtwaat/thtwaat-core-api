"""Unit + quota + billing + webhook tests for Usage Meter."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.usage.dimensions import (
    UsageDimension,
    DEFAULT_PLAN_LIMITS,
    limits_for_plan,
    resolve_plan_key,
)
from app.usage.service import UsageService, month_period


# ── Dimension / plan helpers ──────────────────────────────────────────────────

def test_resolve_plan_key_aliases():
    assert resolve_plan_key("Free") == "free"
    assert resolve_plan_key("growth") == "growth"
    assert resolve_plan_key("pro") == "pro"
    assert resolve_plan_key("business") == "business"
    assert resolve_plan_key("unknown-tier") == "free"


def test_default_plan_limits_cover_required_tiers():
    for tier in ("free", "starter", "pro", "business", "enterprise"):
        limits = limits_for_plan(tier)
        assert limits["max_agents"] >= 1 or tier == "free"
        assert "max_messages" in limits
        assert "max_tokens" in limits
        assert "max_storage" in limits
        assert "max_api_keys" in limits


def test_free_limits_stricter_than_pro():
    free = limits_for_plan("free")
    pro = limits_for_plan("pro")
    assert free["max_messages"] < pro["max_messages"]
    assert free["max_tokens"] < pro["max_tokens"]


def test_month_period_bounds():
    start, end = month_period(datetime(2026, 7, 15, tzinfo=timezone.utc))
    assert start.day == 1
    assert start.month == 7
    assert end.month == 7
    assert end.day == 31


# ── Quota enforcement ─────────────────────────────────────────────────────────

class _FakeMeter:
    def __init__(self):
        self.plan_key = "free"
        self.ai_messages = 99
        self.total_tokens = 1000
        self.max_messages = 100
        self.max_tokens = 50000
        self.max_agents = 1
        self.max_storage = 100
        self.max_domains = 0
        self.max_team_members = 5
        self.max_api_keys = 1
        self.max_templates = 0
        for dim in UsageDimension:
            if not hasattr(self, dim.value):
                setattr(self, dim.value, 0)


def test_check_quota_raises_429_with_payload():
    db = MagicMock()
    svc = UsageService(db)
    meter = _FakeMeter()
    svc.get_or_create_meter = MagicMock(return_value=meter)
    svc._emit_webhook = MagicMock()

    with pytest.raises(HTTPException) as exc:
        svc.check_quota(uuid.uuid4(), UsageDimension.AI_MESSAGES, quantity=2)

    assert exc.value.status_code == 429
    detail = exc.value.detail
    assert detail["error"] == "quota_exceeded"
    assert detail["dimension"] == "ai_messages"
    assert detail["current_usage"] == 99
    assert detail["plan_limit"] == 100
    assert detail["upgrade_url"] == "/billing"
    assert "limit reached" in detail["message"].lower()
    svc._emit_webhook.assert_called()


def test_check_quota_allows_within_limit():
    db = MagicMock()
    svc = UsageService(db)
    meter = _FakeMeter()
    meter.ai_messages = 50
    svc.get_or_create_meter = MagicMock(return_value=meter)

    assert svc.check_quota(uuid.uuid4(), UsageDimension.AI_MESSAGES, quantity=1) is True


# ── Billing hooks ─────────────────────────────────────────────────────────────

def test_apply_plan_limits_upgrades_and_emits_webhook():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    svc = UsageService(db)
    meter = _FakeMeter()
    meter.plan_key = "free"
    meter.max_messages = 100
    svc.get_or_create_meter = MagicMock(return_value=meter)
    svc.repo.save_meter = MagicMock(return_value=meter)
    svc._emit_webhook = MagicMock()

    result = svc.apply_plan_limits(uuid.uuid4(), "pro")
    assert result.plan_key == "pro"
    assert result.max_messages == DEFAULT_PLAN_LIMITS["pro"]["max_messages"]
    svc._emit_webhook.assert_called()
    assert svc._emit_webhook.call_args[0][1] == "subscription.upgraded"


def test_downgrade_to_free_emits_expired():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    svc = UsageService(db)
    meter = _FakeMeter()
    svc.get_or_create_meter = MagicMock(return_value=meter)
    svc.repo.save_meter = MagicMock(return_value=meter)
    svc._emit_webhook = MagicMock()

    svc.downgrade_to_free(uuid.uuid4())
    events = [c[0][1] for c in svc._emit_webhook.call_args_list]
    assert "subscription.expired" in events
    assert meter.plan_key == "free"


def test_activate_company_plan_calls_usage_service():
    from app.payments.subscriptions.service import SubscriptionService

    db = MagicMock()
    company = MagicMock()
    company.credits_balance = 0
    plan = MagicMock()
    plan.name = "Starter"
    plan.max_users = 25
    plan.max_apps = 5
    plan.ai_credits = 100

    with patch("app.usage.service.UsageService") as UsageSvc:
        instance = UsageSvc.return_value
        sub = SubscriptionService(db)
        sub.company_repo = MagicMock()
        sub.company_repo.get_by_id.return_value = company
        sub._activate_company_plan(uuid.uuid4(), plan)
        instance.apply_plan_limits.assert_called_once()


# ── Webhook payload shape ─────────────────────────────────────────────────────

def test_emit_webhook_dispatches_usage_updated():
    db = MagicMock()
    svc = UsageService(db)

    hook = MagicMock()
    hook.url = "https://example.com/hook"
    hook.secret = "whsec_test"
    hook.event_types = ["usage.updated", "quota.exceeded"]

    with patch("app.webhooks.service.WebhookService") as WS:
        ws = WS.return_value
        ws.repo.get_active_by_company.return_value = [hook]
        svc._emit_webhook(uuid.uuid4(), "usage.updated", {"dimension": "ai_messages"})
        ws._dispatch_worker.assert_called_once()
        payload = ws._dispatch_worker.call_args[0][1]
        assert payload["event"] == "usage.updated"
        assert payload["data"]["dimension"] == "ai_messages"


def test_record_enforces_quota_before_increment():
    db = MagicMock()
    svc = UsageService(db)
    meter = _FakeMeter()
    meter.ai_messages = 100
    svc.get_or_create_meter = MagicMock(return_value=meter)
    svc._emit_webhook = MagicMock()

    with pytest.raises(HTTPException) as exc:
        svc.record(uuid.uuid4(), UsageDimension.AI_MESSAGES, 1, enforce=True)
    assert exc.value.status_code == 429
