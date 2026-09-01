"""Call orchestration — the telephony equivalent of chat_runtime/voice_runtime.

Telephony Provider -> Incoming Call -> Call Session -> AgentRuntime.run_turn()
-> Telephony Provider -> Caller.

A "call session" is a ``Conversation`` row with ``channel="call"``; its
``extra_metadata["call"]`` holds ``{call_sid, from, to, provider,
started_at}``. No new DB table — Conversation already has everything a call
session needs (company_id, agent_id, JSONB metadata) — this avoids a
migration for calling state.

Server-side trust model: the caller-supplied ``agent_id``/``conversation_id``
query params on the action URLs are only acted on AFTER the provider's
webhook signature (which covers the exact URL, query string included) has
been verified — forging a signature for a URL with different query params
requires the platform's Twilio auth token. Company/agent/call linkage is
re-checked against the DB regardless, as defense in depth (see
``_resolve_call_session``).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Tuple
from urllib.parse import urlencode
from uuid import UUID

from sqlalchemy.orm import Session

from app.agent_platform.agent_runtime import (
    AgentRuntime,
    agent_capabilities,
    detect_handoff_intent,
    handoff_wait_message,
    resolve_calling_config,
    resolve_locale,
    resolve_provider_and_model,
)
from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.models.conversation import Conversation, Message
from app.agent_platform.telephony.base import TelephonyProviderRegistry
from app.config.settings import settings
from app.usage.dimensions import UsageDimension
from app.usage.service import UsageService

logger = logging.getLogger(__name__)

GATHER_PATH = "/public/v1/telephony/twilio/gather"


def find_agent_by_phone_number(db: Session, to_number: str) -> Optional[AgentConfig]:
    """Route an inbound call to the agent whose ``web_config.calling.phone_number``
    matches. JSONB path lookup — no migration/new table needed."""
    if not to_number:
        return None
    return (
        db.query(AgentConfig)
        .filter(
            AgentConfig.web_config["calling"]["phone_number"].astext == to_number,
            AgentConfig.status == "PUBLISHED",
            AgentConfig.deleted_at.is_(None),
        )
        .first()
    )


def _action_url(path: str, *, agent_id: Any, conversation_id: Any) -> str:
    base = (settings.PUBLIC_API_BASE_URL or "").rstrip("/")
    query = urlencode({"agent_id": str(agent_id), "conversation_id": str(conversation_id)})
    return f"{base}{path}?{query}"


class CallRuntime:
    """Shared execution core for one telephony provider's call lifecycle."""

    @staticmethod
    async def handle_incoming_call(
        db: Session,
        *,
        provider_name: str,
        to_number: str,
        from_number: str,
        call_sid: str,
    ) -> str:
        provider = TelephonyProviderRegistry.get_provider(provider_name)

        agent = find_agent_by_phone_number(db, to_number)
        if not agent:
            logger.warning("telephony: no agent for to_number=%s (call_sid=%s)", to_number, call_sid)
            return provider.build_reject()

        caps = agent_capabilities(agent.web_config)
        if not caps.get("calling", False):
            logger.warning("telephony: calling disabled for agent_id=%s", agent.id)
            return provider.build_reject()

        usage_svc = UsageService(db)
        if not usage_svc.check_quota(
            agent.company_id, UsageDimension.AI_MESSAGES, quantity=1, raise_http=False
        ):
            return provider.build_say_and_hangup(
                text="We're unable to take your call right now. Please try again later."
            )

        calling_cfg = resolve_calling_config(agent)

        conv = Conversation(
            company_id=agent.company_id,
            agent_id=agent.id,
            title=f"Call from {from_number}"[:80],
            channel="call",
            status="open",
            extra_metadata={
                "call": {
                    "call_sid": call_sid,
                    "from": from_number,
                    "to": to_number,
                    "provider": provider_name,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

        usage_svc.record(
            agent.company_id,
            UsageDimension.CALL_COUNT,
            1,
            agent_id=agent.id,
            source="telephony",
            emit_webhook=False,
        )
        usage_svc.record(
            agent.company_id,
            UsageDimension.CONVERSATIONS,
            1,
            agent_id=agent.id,
            source="telephony",
            emit_webhook=False,
        )

        locale = resolve_locale(web_config=agent.web_config) or calling_cfg["language"]
        action_url = _action_url(GATHER_PATH, agent_id=agent.id, conversation_id=conv.id)
        return provider.build_say_and_gather(
            text=calling_cfg["greeting"],
            gather_action_url=action_url,
            language=locale,
        )

    @staticmethod
    async def handle_gather(
        db: Session,
        *,
        provider_name: str,
        agent_id: str,
        conversation_id: str,
        call_sid: str,
        speech_result: str,
    ) -> str:
        provider = TelephonyProviderRegistry.get_provider(provider_name)

        agent, conv = CallRuntime._resolve_call_session(
            db, agent_id=agent_id, conversation_id=conversation_id, call_sid=call_sid
        )
        if not agent or not conv:
            return provider.build_reject()

        caps = agent_capabilities(agent.web_config)
        if not caps.get("calling", False):
            return provider.build_reject()

        calling_cfg = resolve_calling_config(agent)
        locale = resolve_locale(web_config=agent.web_config) or calling_cfg["language"]
        speech = (speech_result or "").strip()

        if (conv.status or "open").lower() == "closed":
            return provider.build_say_and_hangup(text="This conversation has ended. Goodbye.")

        if not speech:
            action_url = _action_url(GATHER_PATH, agent_id=agent.id, conversation_id=conv.id)
            return provider.build_say_and_gather(
                text="Sorry, I didn't catch that. Could you please repeat?",
                gather_action_url=action_url,
                language=locale,
            )

        db.add(Message(conversation_id=conv.id, role="user", content=speech))
        conv.updated_at = datetime.now(timezone.utc)
        db.commit()

        # Reuse the exact same text-handoff detection chat/voice use. A live
        # phone call can't be parked in an async operator queue like chat
        # can — the only real "handoff" for a call is transferring it to a
        # human phone number, if the agent has one configured.
        if caps.get("handoff", True) and detect_handoff_intent(speech):
            conv.status = "pending_human"
            reply = handoff_wait_message(locale)
            db.add(Message(conversation_id=conv.id, role="assistant", content=reply))
            db.commit()
            if calling_cfg.get("human_handoff") and calling_cfg.get("human_handoff_number"):
                return provider.build_say_and_dial(
                    text=reply, phone_number=calling_cfg["human_handoff_number"]
                )
            return provider.build_say_and_hangup(text=reply)

        if agent.status == "PAUSED":
            reply = "This agent is temporarily unavailable. Please try again later."
            db.add(Message(conversation_id=conv.id, role="assistant", content=reply))
            db.commit()
            return provider.build_say_and_hangup(text=reply)

        llm_provider, model = resolve_provider_and_model(agent)
        db.refresh(conv)

        usage_ctx = dict(source="telephony", is_widget=False)
        try:
            result, _sources = await AgentRuntime.run_turn(
                db,
                agent=agent,
                company_id=agent.company_id,
                conv_messages=conv.messages,
                user_content=speech,
                locale=locale,
                provider=llm_provider,
                model=model,
                temperature=agent.temperature or 0.7,
                usage_ctx=usage_ctx,
            )
            reply = result.content or ""
        except Exception as exc:
            logger.error(
                "Call AI turn failed for agent_id=%s call_sid=%s: %s", agent.id, call_sid, exc, exc_info=True
            )
            reply = "I'm having trouble answering right now. Please try again shortly."

        db.add(Message(conversation_id=conv.id, role="assistant", content=reply))
        db.commit()

        action_url = _action_url(GATHER_PATH, agent_id=agent.id, conversation_id=conv.id)
        return provider.build_say_and_gather(text=reply, gather_action_url=action_url, language=locale)

    @staticmethod
    async def handle_status_callback(
        db: Session,
        *,
        call_sid: str,
        call_status: str,
        call_duration: Optional[str],
    ) -> None:
        """Called from the phone number's Twilio-console-configured "Call
        status changes" webhook — a fixed URL with no per-call query params
        (Twilio has no way to attach dynamic query params to that webhook),
        so the call session is looked up by ``call_sid`` alone. Safe because
        the whole request is signature-verified as genuinely from Twilio,
        and ``call_sid`` is Twilio-generated and unguessable."""
        conv = (
            db.query(Conversation)
            .filter(
                Conversation.channel == "call",
                Conversation.extra_metadata["call"]["call_sid"].astext == call_sid,
            )
            .first()
        )
        if not conv:
            logger.warning("telephony: status callback for unknown call_sid=%s", call_sid)
            return
        agent = db.query(AgentConfig).filter(AgentConfig.id == conv.agent_id).first()
        if not agent:
            return

        call_meta = dict((conv.extra_metadata or {}).get("call") or {})
        call_meta["status"] = call_status
        if call_duration:
            call_meta["duration_seconds"] = call_duration
        extra = dict(conv.extra_metadata or {})
        extra["call"] = call_meta
        conv.extra_metadata = extra

        if call_status in ("completed", "failed", "busy", "no-answer", "canceled"):
            if conv.status not in ("pending_human", "human"):
                conv.status = "closed"

        db.add(conv)
        db.commit()

        if call_duration:
            try:
                seconds = int(float(call_duration))
            except (TypeError, ValueError):
                seconds = 0
            if seconds > 0:
                minutes = -(-seconds // 60)  # ceil division
                UsageService(db).record(
                    agent.company_id,
                    UsageDimension.CALL_MINUTES,
                    minutes,
                    agent_id=agent.id,
                    source="telephony",
                    emit_webhook=False,
                )

    @staticmethod
    def _resolve_call_session(
        db: Session, *, agent_id: str, conversation_id: str, call_sid: str
    ) -> Tuple[Optional[AgentConfig], Optional[Conversation]]:
        try:
            agent = db.query(AgentConfig).filter(AgentConfig.id == UUID(str(agent_id))).first()
            conv = db.query(Conversation).filter(Conversation.id == UUID(str(conversation_id))).first()
        except (ValueError, TypeError):
            return None, None

        if not agent or not conv:
            return None, None
        if str(conv.company_id) != str(agent.company_id) or str(conv.agent_id) != str(agent.id):
            logger.warning("telephony: company/agent mismatch for conversation_id=%s", conversation_id)
            return None, None
        stored_sid = ((conv.extra_metadata or {}).get("call") or {}).get("call_sid")
        if stored_sid and stored_sid != call_sid:
            logger.warning("telephony: call_sid mismatch for conversation_id=%s", conversation_id)
            return None, None
        return agent, conv
