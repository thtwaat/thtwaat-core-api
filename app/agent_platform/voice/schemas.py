"""Unified STT/TTS request/response DTOs — mirrors UnifiedChatRequest/Response
(app/agent_platform/schemas.py) so voice providers plug into the same shape
LLM providers do."""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel


class STTResult(BaseModel):
    text: str
    language: Optional[str] = None
    duration_seconds: float = 0.0
    provider: Optional[str] = None
    model: Optional[str] = None


class TTSResult(BaseModel):
    audio_bytes: bytes
    mime_type: str = "audio/mpeg"
    duration_seconds: float = 0.0
    provider: Optional[str] = None
    model: Optional[str] = None

    model_config = {"arbitrary_types_allowed": True}


class VoiceTurnResult(BaseModel):
    """Return value of ``VoiceRuntime.run_voice_turn`` — everything a router
    needs to build either the JSON voice response or (for calls) TwiML."""

    conversation_id: str
    transcript: str
    reply: str
    audio_bytes: bytes
    audio_mime_type: str
    usage: Dict[str, Any]
    status: Optional[str] = None
    handoff: bool = False
    lead: Optional[Dict[str, Any]] = None

    model_config = {"arbitrary_types_allowed": True}
