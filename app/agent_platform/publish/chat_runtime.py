"""Shared public chat execution for JSON + SSE endpoints."""
from __future__ import annotations

import logging
from typing import Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

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
) -> Tuple[str, str, PublicChatUsage]:
    """Returns (reply, conversation_id, usage)."""
    usage_svc = UsageService(db)
    usage_svc.check_quota(api_key.company_id, UsageDimension.AI_MESSAGES, quantity=1)
    usage_svc.check_quota(api_key.company_id, UsageDimension.TOTAL_TOKENS, quantity=1)

    agent = db.query(AgentConfig).filter(AgentConfig.id == api_key.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status != "PUBLISHED":
        raise HTTPException(status_code=403, detail="Agent is not published")
    if str(agent.company_id) != str(api_key.company_id):
        raise HTTPException(status_code=403, detail="Company isolation violation")

    conv: Optional[Conversation] = None
    created_conversation = False
    if session_id:
        try:
            conv = (
                db.query(Conversation)
                .filter(
                    Conversation.id == UUID(session_id),
                    Conversation.company_id == api_key.company_id,
                    Conversation.agent_id == agent.id,
                )
                .first()
            )
        except ValueError:
            conv = None

    if not conv:
        conv = Conversation(
            company_id=api_key.company_id,
            agent_id=agent.id,
            title=(message or "Chat")[:80],
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        created_conversation = True

    db.add(Message(conversation_id=conv.id, role="user", content=message))
    db.commit()

    provider = (agent.web_config or {}).get("provider", "openai")
    model = (agent.web_config or {}).get("model", "gpt-4o-mini")
    system_prompt = agent.system_prompt_template or "You are a helpful assistant."

    agent_kb = db.query(KnowledgeBaseAgent).filter(KnowledgeBaseAgent.agent_id == agent.id).first()
    if agent_kb:
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
                )
        except Exception as exc:
            logger.warning("RAG retrieval failed for public chat: %s", exc)

    db.refresh(conv)
    messages = [{"role": "system", "content": system_prompt}]
    for msg in conv.messages:
        if msg.role in ("user", "assistant"):
            messages.append({"role": msg.role, "content": msg.content})

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
    except HTTPException:
        raise
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
    return reply, str(conv.id), usage
