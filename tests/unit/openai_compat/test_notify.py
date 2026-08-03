"""Week 3 Day 1 — completion webhook notify / enqueue tests."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from app.openai_compat.events import (
    EVENT_COMPLETION_FAILED,
    EVENT_COMPLETION_SUCCEEDED,
    build_completion_event_data,
)
from app.openai_compat.notify import enqueue_completion_webhooks


def test_build_completion_event_data_totals():
    data = build_completion_event_data(
        completion_id="chatcmpl_abc",
        model="thtwaat-stub-mini",
        status="succeeded",
        prompt_tokens=3,
        completion_tokens=7,
        latency_ms=11,
        provider="stub",
    )
    assert data["usage"]["total_tokens"] == 10
    assert data["completion_id"] == "chatcmpl_abc"
    assert data["error"] is None


def test_enqueue_fans_out_matching_hooks_only():
    company_id = uuid.uuid4()
    match = MagicMock()
    match.id = uuid.uuid4()
    match.url = "https://example.com/a"
    match.secret = "whsec_a"
    match.event_types = [EVENT_COMPLETION_SUCCEEDED]

    other = MagicMock()
    other.id = uuid.uuid4()
    other.url = "https://example.com/b"
    other.secret = "whsec_b"
    other.event_types = ["domain.created"]

    star = MagicMock()
    star.id = uuid.uuid4()
    star.url = "https://example.com/star"
    star.secret = "whsec_star"
    star.event_types = ["*"]

    db = MagicMock()
    with patch(
        "app.openai_compat.notify.WebhookRepository"
    ) as repo_cls, patch(
        "app.openai_compat.notify.enqueue_webhook_dispatch"
    ) as enqueue_one:
        repo_cls.return_value.get_active_by_company.return_value = [match, other, star]
        enqueue_one.return_value = {"enqueued": True}

        n = enqueue_completion_webhooks(
            db,
            company_id,
            EVENT_COMPLETION_SUCCEEDED,
            {"completion_id": "chatcmpl_x"},
        )

    assert n == 2
    assert enqueue_one.call_count == 2
    events = {c.kwargs["event"] for c in enqueue_one.call_args_list}
    assert events == {EVENT_COMPLETION_SUCCEEDED}


def test_enqueue_skips_unknown_event():
    db = MagicMock()
    with patch("app.openai_compat.notify._matching_hooks") as hooks:
        n = enqueue_completion_webhooks(db, uuid.uuid4(), "domain.created", {})
    assert n == 0
    hooks.assert_not_called()


def test_enqueue_skips_failed_event_name_still_allowed():
    """completion.failed is a first-class event."""
    company_id = uuid.uuid4()
    hook = MagicMock()
    hook.id = uuid.uuid4()
    hook.url = "https://example.com/fail"
    hook.secret = "whsec_f"
    hook.event_types = [EVENT_COMPLETION_FAILED]

    db = MagicMock()
    with patch(
        "app.openai_compat.notify.WebhookRepository"
    ) as repo_cls, patch(
        "app.openai_compat.notify.enqueue_webhook_dispatch"
    ) as enqueue_one:
        repo_cls.return_value.get_active_by_company.return_value = [hook]
        enqueue_one.return_value = {"enqueued": True}
        n = enqueue_completion_webhooks(
            db, company_id, EVENT_COMPLETION_FAILED, {"status": "failed"}
        )
    assert n == 1
