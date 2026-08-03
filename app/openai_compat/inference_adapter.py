"""Ollama ↔ OpenAI schema adapter (Semester 03 Week 1 Day 1).

Pure mapping helpers — no Redis/DB. CompletionsService / OllamaProvider
consume these so `/v1` stays OpenAI-shaped while talking to a local daemon.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Ollama done_reason → OpenAI finish_reason
_FINISH_MAP = {
    "stop": "stop",
    "length": "length",
    "timeout": "stop",
    "load": "stop",
    "error": "stop",
}


def new_completion_id() -> str:
    return f"chatcmpl_{uuid.uuid4().hex[:24]}"


def build_ollama_chat_payload(
    *,
    model: str,
    messages: List[Dict[str, Any]],
    temperature: Optional[float] = 0.7,
    stream: bool = False,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Native Ollama /api/chat request body."""
    opts = dict(options or {})
    if temperature is not None and "temperature" not in opts:
        opts["temperature"] = float(temperature)
    return {
        "model": model,
        "messages": messages,
        "stream": bool(stream),
        "options": opts,
    }


def map_finish_reason(done_reason: Optional[str]) -> str:
    if not done_reason:
        return "stop"
    return _FINISH_MAP.get(str(done_reason).lower(), "stop")


def extract_ollama_chat_fields(data: Dict[str, Any]) -> tuple[str, int, int, str]:
    """Return (content, prompt_tokens, completion_tokens, finish_reason)."""
    message = data.get("message") or {}
    content = message.get("content") or ""
    if not isinstance(content, str):
        content = str(content)
    prompt_tokens = int(data.get("prompt_eval_count") or 0)
    completion_tokens = int(data.get("eval_count") or 0)
    finish = map_finish_reason(data.get("done_reason"))
    return content, prompt_tokens, completion_tokens, finish


def ollama_chat_to_openai_completion(
    data: Dict[str, Any],
    *,
    model: str,
    completion_id: Optional[str] = None,
    created: Optional[int] = None,
    system_fingerprint: str = "thtwaat-ollama",
) -> Dict[str, Any]:
    """
    Map a non-streaming Ollama /api/chat JSON body to an OpenAI-compatible
    chat.completion object (dict).
    """
    content, prompt_tokens, completion_tokens, finish_reason = extract_ollama_chat_fields(
        data
    )
    cid = completion_id or new_completion_id()
    return {
        "id": cid,
        "object": "chat.completion",
        "created": int(created if created is not None else time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
                "logprobs": None,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "system_fingerprint": system_fingerprint,
    }


def probe_ollama(
    base_url: str,
    *,
    timeout: float = 2.0,
) -> Dict[str, Any]:
    """
    Soft live check: GET /api/tags.
    Never raises — returns {ok, latency_ms, ...}.
    """
    import httpx

    url = (base_url or "").rstrip("/")
    if not url:
        return {"ok": False, "error": "OLLAMA_URL empty"}
    start = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(f"{url}/api/tags")
            latency = round((time.perf_counter() - start) * 1000, 2)
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "latency_ms": latency,
                    "status_code": resp.status_code,
                    "error": (resp.text or "")[:200],
                }
            payload = resp.json() if resp.content else {}
            models = payload.get("models") if isinstance(payload, dict) else None
            count = len(models) if isinstance(models, list) else None
            return {
                "ok": True,
                "latency_ms": latency,
                "models_count": count,
                "url": url,
            }
    except Exception as exc:  # noqa: BLE001 — soft probe
        latency = round((time.perf_counter() - start) * 1000, 2)
        logger.debug("ollama probe failed: %s", exc)
        return {"ok": False, "latency_ms": latency, "error": str(exc), "url": url}
