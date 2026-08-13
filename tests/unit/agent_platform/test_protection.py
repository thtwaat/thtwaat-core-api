"""Unit tests for protected production agent identity helpers."""
from __future__ import annotations

from types import SimpleNamespace

from app.agent_platform.protection import is_protected_agent


def test_is_protected_agent_by_name():
    assert is_protected_agent(name="Viral Awaaz Assistant") is True
    assert is_protected_agent(name="THTWAAT Support Agent") is False


def test_is_protected_agent_by_slug():
    assert is_protected_agent(slug="viral-awaaz-assistant") is True
    assert is_protected_agent(slug="support-bot") is False


def test_is_protected_agent_from_row():
    protected = SimpleNamespace(name="Viral Awaaz Assistant", slug="viral-awaaz-assistant")
    other = SimpleNamespace(name="Hospital Bot", slug="hospital-bot")
    assert is_protected_agent(agent=protected) is True
    assert is_protected_agent(agent=other) is False
