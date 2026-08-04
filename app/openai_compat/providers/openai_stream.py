"""OpenAI HTTP SSE streaming adapter (Sem03 W2 D1)."""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence

import httpx

from app.config.settings import settings
from app.openai_compat.errors import wrap_httpx_error
from app.openai_compat.providers.base import ProviderConfigError
from app.openai_compat.providers.streaming_adapter import StreamDelta, StreamingAdapter

logger = logging.getLogger(__name__)


class OpenAIStreamingAdapter(StreamingAdapter):
    """
    Live OpenAI Chat Completions SSE when OPENAI_API_KEY is set.

    Without a key, raises ProviderConfigError (tests mock this adapter).
    """

    name = "openai"
    BASE_URL = "https://api.openai.com/v1"

    def __init__(self, *, base_url: Optional[str] = None) -> None:
        self._base_url = (base_url or self.BASE_URL).rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None
        self._response: Optional[httpx.Response] = None
        self._cancelled = False

    def _provider_enabled(self) -> bool:
        return bool(getattr(settings, "INFERENCE_ENABLE_OPENAI", True))

    def _resolve_api_key(self) -> str:
        return (settings.OPENAI_API_KEY or "").strip()

    def _auth_headers(self, api_key: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def cancel(self) -> None:
        self._cancelled = True
        try:
            if self._response is not None:
                await self._response.aclose()
        except Exception:  # noqa: BLE001
            logger.debug("openai stream response close failed", exc_info=True)
        try:
            if self._client is not None:
                await self._client.aclose()
        except Exception:  # noqa: BLE001
            logger.debug("openai stream client close failed", exc_info=True)
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
        if not self._provider_enabled():
            raise ProviderConfigError(f"{self.name} provider is disabled")
        api_key = self._resolve_api_key()
        if not api_key:
            raise ProviderConfigError(f"{self.name} API key is not configured")

        body: Dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if temperature is not None:
            body["temperature"] = float(temperature)
        if max_tokens is not None:
            body["max_tokens"] = int(max_tokens)
        if kwargs.get("tools"):
            body["tools"] = kwargs["tools"]
        if kwargs.get("tool_choice") is not None:
            body["tool_choice"] = kwargs["tool_choice"]

        timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
        self._cancelled = False
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers=self._auth_headers(api_key),
        )
        try:
            req = self._client.build_request(
                "POST", f"{self._base_url}/chat/completions", json=body
            )
            self._response = await self._client.send(req, stream=True)
            try:
                self._response.raise_for_status()
            except Exception as exc:
                await self.cancel()
                raise wrap_httpx_error(exc, provider=self.name) from exc

            role_sent = False
            async for line in self._response.aiter_lines():
                if self._cancelled:
                    break
                text = (line or "").strip()
                if not text:
                    continue
                if text.startswith(":"):
                    continue  # SSE comment
                if not text.startswith("data:"):
                    continue
                data_s = text[5:].strip()
                if data_s == "[DONE]":
                    yield StreamDelta(done=True, finish_reason="stop")
                    break
                try:
                    data = json.loads(data_s)
                except json.JSONDecodeError:
                    continue
                choices = data.get("choices") or []
                usage = data.get("usage") or {}
                if choices:
                    delta = (choices[0] or {}).get("delta") or {}
                    finish = (choices[0] or {}).get("finish_reason")
                    if delta.get("role") and not role_sent:
                        role_sent = True
                        yield StreamDelta(role=str(delta.get("role")), content="")
                    content = delta.get("content")
                    if content:
                        if not role_sent:
                            role_sent = True
                            yield StreamDelta(role="assistant", content="")
                        yield StreamDelta(content=str(content), raw=data)
                    if finish:
                        yield StreamDelta(
                            finish_reason=str(finish),
                            prompt_tokens=int(usage["prompt_tokens"])
                            if usage.get("prompt_tokens") is not None
                            else None,
                            completion_tokens=int(usage["completion_tokens"])
                            if usage.get("completion_tokens") is not None
                            else None,
                            done=True,
                            raw=data,
                        )
                        break
                elif usage:
                    # final usage-only chunk
                    yield StreamDelta(
                        prompt_tokens=int(usage.get("prompt_tokens") or 0) or None,
                        completion_tokens=int(usage.get("completion_tokens") or 0) or None,
                        done=True,
                        finish_reason="stop",
                        raw=data,
                    )
                    break
        except Exception as exc:
            if self._cancelled:
                return
            from app.openai_compat.providers.base import InferenceProviderError

            if isinstance(exc, (ProviderConfigError, InferenceProviderError)):
                raise
            raise wrap_httpx_error(exc, provider=self.name) from exc
        finally:
            await self.cancel()


class SyntheticOpenAIStreamingAdapter(StreamingAdapter):
    """Incremental synthetic stream for CI / keyless openai path."""

    name = "openai"

    def __init__(self) -> None:
        self._cancelled = False

    async def cancel(self) -> None:
        self._cancelled = True

    async def stream_chat(
        self,
        *,
        model: str,
        messages: Sequence[Dict[str, Any]],
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamDelta]:
        if not bool(getattr(settings, "INFERENCE_ENABLE_OPENAI", True)):
            raise ProviderConfigError("openai provider is disabled")
        last = ""
        for m in messages:
            if m.get("role") == "user" and m.get("content"):
                last = str(m.get("content"))
        text = f"[openai] {last[:200]}" if last else f"[openai] routed ok for model={model}"
        if max_tokens is not None:
            text = text[: max(1, int(max_tokens) * 4)]
        self._cancelled = False
        yield StreamDelta(role="assistant", content="")
        # word-ish pieces
        buf = ""
        for ch in text:
            if self._cancelled:
                return
            buf += ch
            if ch.isspace() or len(buf) >= 8:
                yield StreamDelta(content=buf)
                buf = ""
        if buf and not self._cancelled:
            yield StreamDelta(content=buf)
        if not self._cancelled:
            # rough token estimate
            completion_tokens = max(1, len(text) // 4)
            prompt_tokens = max(1, len(last) // 4)
            yield StreamDelta(
                finish_reason="stop",
                done=True,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
