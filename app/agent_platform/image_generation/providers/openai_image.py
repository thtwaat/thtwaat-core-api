"""OpenAI image-generation adapter (DALL-E 3 / DALL-E 2 / gpt-image-1) — the
only registered image-generation provider today. Mirrors
app/agent_platform/voice/providers/openai_voice.py: lazily builds an
AsyncOpenAI client from the resolved api_key and self-registers on import.
"""
from __future__ import annotations

import base64
import logging
from typing import List

from app.agent_platform.image_generation.providers.base import ImageGenerationProvider
from app.agent_platform.image_generation.registries import ImageGenerationProviderRegistry
from app.agent_platform.image_generation.schemas import ImageGenerationResult

logger = logging.getLogger(__name__)

# gpt-image-1 always returns base64 and rejects an explicit response_format
# param; dall-e-2/dall-e-3 need response_format="b64_json" requested
# explicitly (default is a temporary provider URL).
_MODELS_WITHOUT_RESPONSE_FORMAT = {"gpt-image-1"}


class OpenAIImageProvider(ImageGenerationProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key=api_key)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            if not self.api_key:
                raise RuntimeError("OPENAI_API_KEY is not configured — image generation unavailable.")
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        prompt: str,
        *,
        model: str,
        size: str = "1024x1024",
        quality: str = "standard",
        n: int = 1,
    ) -> List[ImageGenerationResult]:
        client = self._get_client()
        kwargs = {"model": model, "prompt": prompt, "size": size, "n": n}
        # dall-e-2 doesn't accept a "quality" param; dall-e-3/gpt-image-1 do.
        if model != "dall-e-2":
            kwargs["quality"] = quality
        if model not in _MODELS_WITHOUT_RESPONSE_FORMAT:
            kwargs["response_format"] = "b64_json"

        response = await client.images.generate(**kwargs)

        results: List[ImageGenerationResult] = []
        for item in response.data or []:
            b64 = getattr(item, "b64_json", None)
            if not b64:
                # Defensive fallback — should not happen given the kwargs above.
                raise RuntimeError("Image provider did not return base64 image data.")
            results.append(
                ImageGenerationResult(
                    image_bytes=base64.b64decode(b64),
                    mime_type="image/png",
                    provider="openai",
                    model=model,
                    revised_prompt=getattr(item, "revised_prompt", None),
                )
            )
        return results


ImageGenerationProviderRegistry.register("openai", OpenAIImageProvider)
