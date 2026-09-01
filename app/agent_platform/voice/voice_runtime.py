"""Voice turn orchestration — the audio equivalent of
``app/agent_platform/publish/chat_runtime.py``.

Audio in -> STTProvider.transcribe() -> AgentRuntime.run_turn() (the shared
AI brain — identical to text chat) -> TTSProvider.synthesize() -> audio out.
Conversation/Message persistence, capability gating, handoff and locale all
reuse the exact same helpers text chat uses; only audio codec handling and
STT/TTS provider selection are voice-specific.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.agent_platform.agent_runtime import (
    AI_BLOCKED_STATUSES,
    AgentRuntime,
    agent_capabilities,
    conversation_closed_message,
    detect_handoff_intent,
    handoff_wait_message,
    resolve_locale,
    resolve_provider_and_model,
    resolve_voice_config,
)
from app.agent_platform.models.conversation import Conversation, Message
from app.agent_platform.voice.credentials import resolve_voice_api_key
from app.agent_platform.voice.registries import STTProviderRegistry, TTSProviderRegistry
from app.agent_platform.voice.schemas import VoiceTurnResult
from app.usage.dimensions import UsageDimension
from app.usage.service import UsageService

logger = logging.getLogger(__name__)


def _get_or_create_conversation(
    db: Session,
    *,
    company_id: Any,
    agent: Any,
    channel: str,
    session_id: Optional[str],
    title_hint: str,
) -> Conversation:
    conv: Optional[Conversation] = None
    if session_id:
        try:
            conv = (
                db.query(Conversation)
                .options(joinedload(Conversation.messages))
                .filter(
                    Conversation.id == UUID(session_id),
                    Conversation.company_id == company_id,
                    Conversation.agent_id == agent.id,
                )
                .first()
            )
        except ValueError:
            conv = None

    if conv:
        return conv

    conv = Conversation(
        company_id=company_id,
        agent_id=agent.id,
        title=title_hint[:80],
        channel=channel,
        status="open",
        extra_metadata={},
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


class VoiceRuntime:
    """Shared execution core for a single voice (audio) turn."""

    @staticmethod
    async def run_voice_turn(
        db: Session,
        *,
        agent: Any,
        company_id: Any,
        channel: str,
        audio_bytes: bytes,
        audio_mime_type: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        usage_ctx: Optional[Dict[str, Any]] = None,
    ) -> VoiceTurnResult:
        caps = agent_capabilities(getattr(agent, "web_config", None))
        AgentRuntime.check_voice_request(caps)

        usage_svc = UsageService(db)
        usage_svc.check_quota(company_id, UsageDimension.AI_MESSAGES, quantity=1)
        usage_svc.check_quota(company_id, UsageDimension.TOTAL_TOKENS, quantity=1)

        voice_cfg = resolve_voice_config(agent)
        api_key = resolve_voice_api_key(voice_cfg["provider"])
        if not api_key:
            raise HTTPException(
                status_code=503,
                detail=f"Voice provider '{voice_cfg['provider']}' is not configured.",
            )

        stt = STTProviderRegistry.get_provider(voice_cfg["provider"], api_key)
        try:
            stt_result = await stt.transcribe(
                audio_bytes, mime_type=audio_mime_type, language=voice_cfg["language"]
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("STT transcription failed for agent_id=%s: %s", agent.id, exc, exc_info=True)
            raise HTTPException(status_code=502, detail="Speech-to-text failed. Please try again.") from exc

        transcript = (stt_result.text or "").strip()

        conv = _get_or_create_conversation(
            db,
            company_id=company_id,
            agent=agent,
            channel=channel,
            session_id=session_id,
            title_hint=transcript or "Voice chat",
        )
        if metadata:
            existing = dict(conv.extra_metadata or {})
            existing.update(metadata)
            conv.extra_metadata = existing
            db.add(conv)
            db.commit()

        locale = (
            resolve_locale(metadata=conv.extra_metadata, web_config=agent.web_config)
            or voice_cfg["language"]
        )

        if stt_result.duration_seconds:
            usage_svc.record(
                company_id,
                UsageDimension.AUDIO_INPUT_SECONDS,
                max(1, round(stt_result.duration_seconds)),
                agent_id=agent.id,
                source=(usage_ctx or {}).get("source", "voice"),
                emit_webhook=False,
            )

        if not transcript:
            reply = "Sorry, I didn't catch that. Could you please repeat?"
            return await VoiceRuntime._synthesize_and_return(
                db,
                agent=agent,
                conv=conv,
                voice_cfg=voice_cfg,
                api_key=api_key,
                transcript="",
                reply=reply,
                usage={},
                status=conv.status,
                handoff=False,
            )

        db.add(Message(conversation_id=conv.id, role="user", content=transcript))
        conv.updated_at = datetime.now(timezone.utc)
        db.commit()

        status = (conv.status or "open").lower()
        if status in AI_BLOCKED_STATUSES:
            reply = conversation_closed_message(locale) if status == "closed" else handoff_wait_message(locale)
            db.add(Message(conversation_id=conv.id, role="assistant", content=reply))
            db.commit()
            return await VoiceRuntime._synthesize_and_return(
                db,
                agent=agent,
                conv=conv,
                voice_cfg=voice_cfg,
                api_key=api_key,
                transcript=transcript,
                reply=reply,
                usage={},
                status=conv.status,
                handoff=True,
            )

        if caps.get("handoff", True) and detect_handoff_intent(transcript):
            conv.status = "pending_human"
            reply = handoff_wait_message(locale)
            db.add(Message(conversation_id=conv.id, role="assistant", content=reply))
            db.add(conv)
            db.commit()
            return await VoiceRuntime._synthesize_and_return(
                db,
                agent=agent,
                conv=conv,
                voice_cfg=voice_cfg,
                api_key=api_key,
                transcript=transcript,
                reply=reply,
                usage={},
                status=conv.status,
                handoff=True,
            )

        if agent.status == "PAUSED":
            reply = "This agent is paused. Please try again later."
            db.add(Message(conversation_id=conv.id, role="assistant", content=reply))
            db.commit()
            return await VoiceRuntime._synthesize_and_return(
                db,
                agent=agent,
                conv=conv,
                voice_cfg=voice_cfg,
                api_key=api_key,
                transcript=transcript,
                reply=reply,
                usage={},
                status=conv.status,
                handoff=False,
            )

        provider, model = resolve_provider_and_model(agent)
        db.refresh(conv)

        try:
            result, _sources = await AgentRuntime.run_turn(
                db,
                agent=agent,
                company_id=company_id,
                conv_messages=conv.messages,
                user_content=transcript,
                locale=locale,
                provider=provider,
                model=model,
                temperature=agent.temperature or 0.7,
                usage_ctx=usage_ctx,
            )
            reply = result.content or ""
            usage = {
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "total_tokens": result.total_tokens,
                "estimated_cost": result.estimated_cost,
                "provider": result.provider,
                "model": result.model,
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Voice turn AI call failed for agent_id=%s: %s", agent.id, exc, exc_info=True)
            reply = "I encountered an error while generating the answer. Please try again later."
            usage = {}

        db.add(Message(conversation_id=conv.id, role="assistant", content=reply))
        db.commit()

        return await VoiceRuntime._synthesize_and_return(
            db,
            agent=agent,
            conv=conv,
            voice_cfg=voice_cfg,
            api_key=api_key,
            transcript=transcript,
            reply=reply,
            usage=usage,
            status=conv.status,
            handoff=False,
        )

    @staticmethod
    async def _synthesize_and_return(
        db: Session,
        *,
        agent: Any,
        conv: Conversation,
        voice_cfg: Dict[str, Any],
        api_key: str,
        transcript: str,
        reply: str,
        usage: Dict[str, Any],
        status: Optional[str],
        handoff: bool,
    ) -> VoiceTurnResult:
        tts = TTSProviderRegistry.get_provider(voice_cfg["provider"], api_key)
        try:
            tts_result = await tts.synthesize(
                reply,
                voice_id=voice_cfg["voice_id"],
                language=voice_cfg["language"],
                speed=voice_cfg["speed"],
            )
        except Exception as exc:
            logger.error("TTS synthesis failed for agent_id=%s: %s", agent.id, exc, exc_info=True)
            raise HTTPException(status_code=502, detail="Text-to-speech failed. Please try again.") from exc

        if tts_result.duration_seconds:
            UsageService(db).record(
                conv.company_id,
                UsageDimension.AUDIO_OUTPUT_SECONDS,
                max(1, round(tts_result.duration_seconds)),
                agent_id=agent.id,
                source="voice",
                emit_webhook=False,
            )

        return VoiceTurnResult(
            conversation_id=str(conv.id),
            transcript=transcript,
            reply=reply,
            audio_bytes=tts_result.audio_bytes,
            audio_mime_type=tts_result.mime_type,
            usage=usage,
            status=status,
            handoff=handoff,
        )
