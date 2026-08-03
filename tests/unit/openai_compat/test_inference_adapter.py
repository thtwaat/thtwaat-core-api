"""Semester 03 Week 1 Day 1 — Ollama ↔ OpenAI adapter."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.openai_compat.inference_adapter import (
    build_ollama_chat_payload,
    extract_ollama_chat_fields,
    map_finish_reason,
    ollama_chat_to_openai_completion,
    probe_ollama,
)


@pytest.mark.unit
def test_build_ollama_chat_payload():
    payload = build_ollama_chat_payload(
        model="llama3.2",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.2,
        stream=False,
    )
    assert payload["model"] == "llama3.2"
    assert payload["stream"] is False
    assert payload["options"]["temperature"] == 0.2
    assert payload["messages"][0]["content"] == "hi"


@pytest.mark.unit
def test_extract_and_map_openai_completion():
    ollama = {
        "model": "llama3.2",
        "message": {"role": "assistant", "content": "Hello there"},
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 12,
        "eval_count": 4,
    }
    content, pin, cout, finish = extract_ollama_chat_fields(ollama)
    assert content == "Hello there"
    assert pin == 12
    assert cout == 4
    assert finish == "stop"

    openai = ollama_chat_to_openai_completion(
        ollama, model="llama3.2", completion_id="chatcmpl_test", created=1_700_000_000
    )
    assert openai["object"] == "chat.completion"
    assert openai["id"] == "chatcmpl_test"
    assert openai["choices"][0]["message"]["content"] == "Hello there"
    assert openai["usage"]["total_tokens"] == 16
    assert openai["system_fingerprint"].startswith("thtwaat-ollama")


@pytest.mark.unit
def test_map_finish_reason_unknown_defaults_stop():
    assert map_finish_reason(None) == "stop"
    assert map_finish_reason("length") == "length"
    assert map_finish_reason("weird") == "stop"


@pytest.mark.unit
def test_probe_ollama_ok():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"models":[{"name":"a"},{"name":"b"}]}'
    mock_resp.json.return_value = {"models": [{"name": "a"}, {"name": "b"}]}
    with patch("httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        out = probe_ollama("http://ollama:11434")
    assert out["ok"] is True
    assert out["models_count"] == 2


@pytest.mark.unit
def test_probe_ollama_down():
    with patch("httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.side_effect = ConnectionError(
            "refused"
        )
        out = probe_ollama("http://ollama:11434")
    assert out["ok"] is False
    assert "error" in out


@pytest.mark.unit
def test_health_includes_ollama_live(monkeypatch):
    monkeypatch.setattr(
        "app.deploy.health.settings.OLLAMA_URL",
        "http://ollama:11434",
        raising=False,
    )
    monkeypatch.setattr(
        "app.deploy.health.settings.OPENAI_API_KEY",
        None,
        raising=False,
    )
    with patch(
        "app.openai_compat.inference_adapter.probe_ollama",
        return_value={"ok": True, "latency_ms": 1.0, "models_count": 1},
    ):
        from app.deploy.health import check_ai_providers

        result = check_ai_providers()
    assert result["providers"]["ollama"] is True
    assert result["ollama_live"]["ok"] is True
