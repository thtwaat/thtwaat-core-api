"""Ollama NDJSON streaming adapter (Sem03 W2 D1)."""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, Optional, Sequence

import httpx

from app.config.settings import settings
from app.openai_compat.errors import wrap_httpx_error
from app.openai_compat.inference_adapter import (
    build_ollama_chat_payload,
    map_finish_reason,
)
from app.openai_compat.providers.base import ProviderConfigError
from app.openai_compat.providers.streaming_adapter import StreamDelta, StreamingAdapter

logger = logging.getLogger(__name__)


class OllamaStreamingAdapter(StreamingAdapter):
    name = "ollama"

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._response: Optional[httpx.Response] = None
        self._cancelled = False

    def _base_url(self) -> str:
        url = (settings.OLLAMA_URL or "").rstrip("/")
        if not url:
            raise ProviderConfigError("OLLAMA_URL is not configured")
        return url

    def _timeout(self) -> httpx.Timeout:
        raw = getattr(settings, "INFERENCE_OLLAMA_TIMEOUT_SECONDS", 120.0)
        try:
            total = max(1.0, float(raw))
        except (TypeError, ValueError):
            total = 120.0
        # Long streams: generous read; connect stays short
        return httpx.Timeout(connect=10.0, read=total, write=30.0, pool=10.0)

    async def cancel(self) -> None:
        self._cancelled = True
        try:
            if self._response is not None:
                await self._response.aclose()
        except Exception:  # noqa: BLE001
            logger.debug("ollama stream response close failed", exc_info=True)
        try:
            if self._client is not None:
                await self._client.aclose()
        except Exception:  # noqa: BLE001
            logger.debug("ollama stream client close failed", exc_info=True)
        self._response = None
        self._client = None

    async def stream_chat(
        self,
        *,
        model: str,
        messages: Sequence[Dict[str, Any]],
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamDelta]:
        if not bool(getattr(settings, "INFERENCE_ENABLE_OLLAMA", True)):
            raise ProviderConfigError("ollama provider is disabled")
        base = self._base_url()
        payload = build_ollama_chat_payload(
            model=model,
            messages=list(messages),
            temperature=temperature,
            stream=True,
        )
        if max_tokens is not None:
            payload.setdefault("options", {})["num_predict"] = int(max_tokens)

        self._cancelled = False
        self._client = httpx.AsyncClient(timeout=self._timeout())
        try:
            req = self._client.build_request("POST", f"{base}/api/chat", json=payload)
            self._response = await self._client.send(req, stream=True)
            try:
                self._response.raise_for_status()
            except Exception as exc:
                body = ""
                try:
                    body = (await self._response.aread()).decode("utf-8", errors="replace")[:300]
                except Exception:  # noqa: BLE001
                    pass
                await self.cancel()
                raise wrap_httpx_error(exc, provider=self.name) from exc

            role_sent = False
            async for line in self._response.aiter_lines():
                if self._cancelled:
                    break
                text = (line or "").strip()
                if not text:
                    continue
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    logger.debug("ollama stream skip bad json: %s", text[:80])
                    continue
                if not role_sent:
                    role_sent = True
                    yield StreamDelta(role="assistant", content="")
                msg = data.get("message") or {}
                piece = msg.get("content") or ""
                if piece:
                    yield StreamDelta(content=str(piece), raw=data)
                if data.get("done"):
                    finish = map_finish_reason(data.get("done_reason"))
                    yield StreamDelta(
                        finish_reason=finish,
                        prompt_tokens=int(data.get("prompt_eval_count") or 0) or None,
                        completion_tokens=int(data.get("eval_count") or 0) or None,
                        done=True,
                        raw=data,
                    )
                    break
        except Exception as exc:
            if self._cancelled:
                return
            if isinstance(exc, (ProviderConfigError,)):
                raise
            # Already wrapped?
            from app.openai_compat.providers.base import InferenceProviderError

            if isinstance(exc, InferenceProviderError):
                raise
            raise wrap_httpx_error(exc, provider=self.name) from exc
        finally:
            await self.cancel()
