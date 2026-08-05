"""Shared public chat execution for JSON + SSE endpoints."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.agent_platform.agent_runtime import (
    AI_BLOCKED_STATUSES,
    agent_capabilities,
    conversation_closed_message,
    detect_handoff_intent,
    extract_lead,
    handoff_wait_message,
    language_system_instruction,
    memory_message_window,
    merge_lead_into_metadata,
    resolve_locale,
    to_gateway_role,
)
from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.models.api_key import AgentApiKey
from app.agent_platform.models.conversation import Conversation, Message
from app.agent_platform.knowledge.models.knowledge_base import KnowledgeBaseAgent
from app.agent_platform.knowledge.services import KnowledgeService
from app.agent_platform.gateway.service import AIGatewayService
from app.agent_platform.schemas import UnifiedChatRequest
from app.agent_platform.publish.schemas import PublicChatUsage
from app.usage.dimensions import UsageDimension
from app.usage.service import UsageService

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """\
You are a helpful, accurate assistant. Answer the user's question using ONLY \
the context provided below. If the answer is not in the context, say \
"I don't have enough information to answer that."

Context:
{context}
"""


async def run_public_chat(
    db: Session,
    api_key: AgentApiKey,
    message: str,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, PublicChatUsage, Dict[str, Any]]:
    """Returns (reply, conversation_id, usage, extras).

    ``extras`` may include status, handoff, lead, thinking_stages.
    """
    async for event in iter_public_chat_events(
        db, api_key, message, session_id=session_id, metadata=metadata
    ):
        if event[0] == "done":
            payload = event[1]
            usage = PublicChatUsage(**(payload.get("usage") or {}))
            return (
                payload.get("reply") or "",
                payload.get("conversation_id") or "",
                usage,
                {
                    "status": payload.get("status"),
                    "handoff": payload.get("handoff", False),
                    "lead": payload.get("lead"),
                },
            )
        if event[0] == "error":
            raise HTTPException(status_code=400, detail=event[1].get("message") or "Chat failed")
    raise HTTPException(status_code=500, detail="Chat produced no result")


async def iter_public_chat_events(
    db: Session,
    api_key: AgentApiKey,
    message: str,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AsyncIterator[Tuple[str, Dict[str, Any]]]:
    """Yield SSE-ready events: thinking → token* → done | error."""
    usage_svc = UsageService(db)
    usage_svc.check_quota(api_key.company_id, UsageDimension.AI_MESSAGES, quantity=1)
    usage_svc.check_quota(api_key.company_id, UsageDimension.TOTAL_TOKENS, quantity=1)

    yield ("thinking", {"stage": "understanding", "message": "Understanding your message…"})

    agent = db.query(AgentConfig).filter(AgentConfig.id == api_key.agent_id).first()
    if not agent:
        yield ("error", {"message": "Agent not found"})
        return
    if agent.status != "PUBLISHED":
        yield ("error", {"message": "Agent is not published"})
        return
    if str(agent.company_id) != str(api_key.company_id):
        yield ("error", {"message": "Company isolation violation"})
        return

    caps = agent_capabilities(agent.web_config)
    locale = resolve_locale(metadata=metadata, web_config=agent.web_config)

    conv: Optional[Conversation] = None
    created_conversation = False
    if session_id:
        try:
            conv = (
                db.query(Conversation)
                .options(joinedload(Conversation.messages))
                .filter(
                    Conversation.id == UUID(session_id),
                    Conversation.company_id == api_key.company_id,
                    Conversation.agent_id == agent.id,
                )
                .first()
            )
        except ValueError:
            conv = None

    meta = dict(metadata or {})
    lead = extract_lead(meta) if caps.get("lead_capture", True) else None

    if not conv:
        extra = merge_lead_into_metadata(meta, lead) if lead else dict(meta)
        if locale:
            extra["locale"] = locale
        conv = Conversation(
            company_id=api_key.company_id,
            agent_id=agent.id,
            title=(message or "Chat")[:80],
            channel="widget",
            status="open",
            extra_metadata=extra,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        created_conversation = True
    else:
        existing = dict(conv.extra_metadata or {})
        if meta:
            existing.update(meta)
        if lead:
            existing = merge_lead_into_metadata(existing, lead)
        if locale:
            existing["locale"] = locale
        conv.extra_metadata = existing
        db.add(conv)
        db.commit()

    locale = resolve_locale(metadata=conv.extra_metadata, web_config=agent.web_config) or locale

    # Persist visitor message
    db.add(Message(conversation_id=conv.id, role="user", content=message))
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()

    # Closed / human-owned threads: do not call AI
    status = (conv.status or "open").lower()
    if status in AI_BLOCKED_STATUSES:
        if status == "closed":
            reply = conversation_closed_message(locale)
        else:
            reply = handoff_wait_message(locale)
        db.add(Message(conversation_id=conv.id, role="assistant", content=reply))
        db.commit()
        usage = PublicChatUsage()
        yield (
            "done",
            {
                "conversation_id": str(conv.id),
                "reply": reply,
                "usage": usage.model_dump(),
                "status": conv.status,
                "handoff": True,
                "lead": (conv.extra_metadata or {}).get("lead"),
            },
        )
        return

    # Keyword handoff
    if caps.get("handoff", True) and detect_handoff_intent(message):
        yield ("thinking", {"stage": "handoff", "message": "Connecting you to a human…"})
        conv.status = "pending_human"
        reply = handoff_wait_message(locale)
        db.add(Message(conversation_id=conv.id, role="assistant", content=reply))
        db.add(conv)
        db.commit()
        usage = PublicChatUsage()
        yield (
            "done",
            {
                "conversation_id": str(conv.id),
                "reply": reply,
                "usage": usage.model_dump(),
                "status": conv.status,
                "handoff": True,
                "lead": (conv.extra_metadata or {}).get("lead"),
            },
        )
        return

    provider = (agent.web_config or {}).get("provider", "openai")
    model = (agent.web_config or {}).get("model", "gpt-4o-mini")
    system_prompt = agent.system_prompt_template or "You are a helpful assistant."
    if caps.get("multilingual", True):
        system_prompt = system_prompt + language_system_instruction(locale)

    agent_kb = db.query(KnowledgeBaseAgent).filter(KnowledgeBaseAgent.agent_id == agent.id).first()
    if agent_kb:
        yield ("thinking", {"stage": "searching", "message": "Searching knowledge…"})
        try:
            sources = KnowledgeService.search_knowledge_base(
                db=db,
                query=message,
                top_k=5,
                company_id=api_key.company_id,
                kb_id=agent_kb.knowledge_base_id,
            )
            try:
                usage_svc.record(
                    api_key.company_id,
                    UsageDimension.KNOWLEDGE_SEARCHES,
                    1,
                    agent_id=agent.id,
                    source="public_chat",
                    emit_webhook=False,
                )
            except Exception:
                pass
            if sources:
                blocks = [
                    f"[{i}] (Source: {src.document_name})\n{src.text}"
                    for i, src in enumerate(sources, start=1)
                ]
                context = "\n\n---\n\n".join(blocks)
                system_prompt = (
                    _SYSTEM_PROMPT_TEMPLATE.format(context=context)
                    + "\n\nOriginal Instructions: "
                    + (agent.system_prompt_template or "")
                    + language_system_instruction(locale)
                )
        except Exception as exc:
            logger.warning("RAG retrieval failed for public chat: %s", exc)

    yield ("thinking", {"stage": "generating", "message": "Thinking…"})

    db.refresh(conv)
    prior = memory_message_window(
        conv.messages,
        enabled=caps.get("memory", True),
        max_messages=40,
    )
    messages = [{"role": "system", "content": system_prompt}]
    for msg in prior:
        role = to_gateway_role(msg.role)
        if role in ("user", "assistant", "system", "tool"):
            messages.append({"role": role, "content": msg.content})

    chat_request = UnifiedChatRequest(
        company_id=str(api_key.company_id),
        agent_id=str(agent.id),
        provider=provider,
        model=model,
        messages=messages,
        temperature=agent.temperature or 0.7,
        max_tokens=1024,
    )

    try:
        result = await AIGatewayService.process_request(
            chat_request,
            db=db,
            api_key_id=str(api_key.id),
            widget_id=agent.widget_id,
            source="public_chat",
            is_widget=True,
            create_conversation=created_conversation,
        )
        reply = result.content or ""
        usage = PublicChatUsage(
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            estimated_cost=result.estimated_cost,
            provider=result.provider,
            model=result.model,
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
        yield ("error", {"message": detail})
        return
    except Exception as exc:
        logger.error("Public chat AI failed: %s", exc, exc_info=True)
        reply = "I encountered an error while generating the answer. Please try again later."
        usage = PublicChatUsage()

    db.add(Message(conversation_id=conv.id, role="assistant", content=reply))
    db.commit()

    logger.info(
        "audit_event=public_chat company_id=%s agent_id=%s conversation_id=%s",
        api_key.company_id,
        agent.id,
        conv.id,
    )

    # Progressive tokens for UX
    chunk = max(1, len(reply) // 48) if reply else 1
    i = 0
    while i < len(reply):
        nxt = min(len(reply), i + chunk)
        yield ("token", {"text": reply[i:nxt]})
        i = nxt

    yield (
        "done",
        {
            "conversation_id": str(conv.id),
            "reply": reply,
            "usage": usage.model_dump(),
            "status": conv.status,
            "handoff": False,
            "lead": (conv.extra_metadata or {}).get("lead"),
        },
    )
