"""Unified Inbox conversation service — filters, unread, assignment (Module 2)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.agent_platform.conversation_schemas import ConversationUpdate
from app.agent_platform.models.conversation import Conversation, Message
from app.agent_platform.services.conversation_service import (
    ConversationService,
    _enrich,
    _is_unread,
)


def _conv(**kwargs) -> Conversation:
    now = datetime.now(timezone.utc)
    base = dict(
        id=uuid4(),
        company_id=uuid4(),
        agent_id=uuid4(),
        title="Hello",
        channel="widget",
        status="open",
        assigned_to_user_id=None,
        last_read_at=None,
        extra_metadata={},
        created_at=now,
        updated_at=now,
        messages=[],
    )
    base.update(kwargs)
    return SimpleNamespace(**base)  # type: ignore[return-value]


@pytest.mark.unit
def test_unread_when_never_read_and_has_user_message():
    now = datetime.now(timezone.utc)
    conv = _conv(last_read_at=None)
    conv.messages = [
        SimpleNamespace(role="user", content="hi", created_at=now),
        SimpleNamespace(role="assistant", content="yo", created_at=now + timedelta(seconds=1)),
    ]
    row = _enrich(conv)  # type: ignore[arg-type]
    assert row.unread is True
    assert row.message_count == 2
    assert row.channel == "widget"
    assert row.last_message_preview == "yo"


@pytest.mark.unit
def test_read_when_last_read_after_user_message():
    now = datetime.now(timezone.utc)
    assert _is_unread(
        SimpleNamespace(last_read_at=now + timedelta(seconds=5)),
        now,
    ) is False
    assert _is_unread(SimpleNamespace(last_read_at=now - timedelta(seconds=5)), now) is True


@pytest.mark.unit
def test_invalid_channel_filter_raises(monkeypatch):
    class _Q:
        def options(self, *a, **k):
            return self

        def filter(self, *a, **k):
            return self

        def outerjoin(self, *a, **k):
            return self

        def distinct(self):
            return self

        def order_by(self, *a, **k):
            return self

        def offset(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

        def all(self):
            return []

    class _Db:
        def query(self, *a, **k):
            return _Q()

    with pytest.raises(HTTPException) as ei:
        ConversationService.get_conversations(_Db(), uuid4(), channel="whatsapp")  # type: ignore[arg-type]
    assert ei.value.status_code == 400


@pytest.mark.unit
def test_update_status_and_assign(monkeypatch):
    company_id = uuid4()
    conv_id = uuid4()
    user_id = uuid4()
    now = datetime.now(timezone.utc)
    conv = Conversation(
        id=conv_id,
        company_id=company_id,
        agent_id=uuid4(),
        title="t",
        channel="dashboard",
        status="open",
        assigned_to_user_id=None,
        last_read_at=None,
        extra_metadata={},
    )
    conv.created_at = now
    conv.updated_at = now
    conv.messages = []

    class _Q:
        def __init__(self):
            self._obj = conv

        def options(self, *a, **k):
            return self

        def filter(self, *a, **k):
            return self

        def first(self):
            return self._obj

    class _Db:
        def query(self, *a, **k):
            return _Q()

        def add(self, obj):
            pass

        def commit(self):
            pass

        def refresh(self, obj):
            pass

    out = ConversationService.update_conversation(
        _Db(),  # type: ignore[arg-type]
        conv_id,
        company_id,
        ConversationUpdate(status="pending_human", assigned_to_user_id=user_id, mark_read=True),
    )
    assert out.status == "pending_human"
    assert out.assigned_to_user_id == user_id
    assert out.last_read_at is not None
