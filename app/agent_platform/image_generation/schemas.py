"""Unified image-generation request/result DTO — mirrors STTResult/TTSResult
(app/agent_platform/voice/schemas.py) so image providers plug into the same
shape STT/TTS providers do."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ImageGenerationResult(BaseModel):
    image_bytes: bytes
    mime_type: str = "image/png"
    provider: Optional[str] = None
    model: Optional[str] = None
    revised_prompt: Optional[str] = None

    model_config = {"arbitrary_types_allowed": True}
