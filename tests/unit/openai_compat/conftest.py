"""Shared fixtures for openai_compat unit tests."""
from __future__ import annotations

import pytest


class _FakeCompletionLog:
    """Avoid SQLAlchemy mapper configure cascades in unit tests."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


@pytest.fixture(autouse=True)
def _fake_completion_log_orm(monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.service.OpenAICompletionLog",
        _FakeCompletionLog,
    )
