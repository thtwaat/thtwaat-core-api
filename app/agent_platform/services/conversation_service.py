import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException

from app.agent_platform.models.conversation import (
    INBOX_CHANNELS,
    INBOX_STATUSES,
    Conversation,
    Message,
)
from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.knowledge.models.knowledge_base import KnowledgeBaseAgent
from app.agent_platform.conversation_schemas import (
    ConversationCreate,
    ConversationDetailResponse,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
)
from app.agent_platform.knowledge.services import KnowledgeService
from app.agent_platform.gateway.service import AIGatewayService
from app.agent_platform.schemas import UnifiedChatRequest

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """\
You are a helpful, accurate assistant. Answer the user's question using ONLY \
the context provided below. If the answer is not in the context, say \
"I don't have enough information to answer that."

Context:
{context}
"""


def _preview(text: Optional[str], limit: int = 120) -> Optional[str]:
    if not text:
        return None
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def _is_unread(conv: Conversation, last_user_at: Optional[datetime]) -> bool:
    if last_user_at is None:
        return False
    if conv.last_read_at is None:
        return True
    # Normalize aware/naive comparison
    read_at = conv.last_read_at
    msg_at = last_user_at
    if read_at.tzinfo is None and msg_at.tzinfo is not None:
        read_at = read_at.replace(tzinfo=timezone.utc)
    if msg_at.tzinfo is None and read_at.tzinfo is not None:
        msg_at = msg_at.replace(tzinfo=timezone.utc)
    return msg_at > read_at


def _enrich(conv: Conversation) -> ConversationResponse:
    messages = list(conv.messages or [])
    messages_sorted = sorted(messages, key=lambda m: m.created_at or datetime.min.replace(tzinfo=timezone.utc))
    last = messages_sorted[-1] if messages_sorted else None
    last_user = next((m for m in reversed(messages_sorted) if m.role == "user"), None)
    return ConversationResponse(
        id=conv.id,
        company_id=conv.company_id,
        agent_id=conv.agent_id,
        title=conv.title,
        channel=getattr(conv, "channel", None) or "dashboard",
        status=getattr(conv, "status", None) or "open",
        assigned_to_user_id=getattr(conv, "assigned_to_user_id", None),
        last_read_at=getattr(conv, "last_read_at", None),
        extra_metadata=dict(getattr(conv, "extra_metadata", None) or {}),
        message_count=len(messages),
        last_message_preview=_preview(last.content if last else None),
        last_message_at=last.created_at if last else None,
        unread=_is_unread(conv, last_user.created_at if last_user else None),
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


def _detail(conv: Conversation) -> ConversationDetailResponse:
    base = _enrich(conv)
    messages = sorted(
        list(conv.messages or []),
        key=lambda m: m.created_at or datetime.min.replace(tzinfo=timezone.utc),
    )
    return ConversationDetailResponse(
        **base.model_dump(),
        messages=[MessageResponse.model_validate(m) for m in messages],
    )


class ConversationService:

    @staticmethod
    def get_conversations(
        db: Session,
        company_id: UUID,
        *,
        skip: int = 0,
        limit: int = 50,
        q: Optional[str] = None,
        agent_id: Optional[UUID] = None,
        channel: Optional[str] = None,
        status: Optional[str] = None,
        assigned_to_user_id: Optional[UUID] = None,
        unread_only: bool = False,
    ) -> List[ConversationResponse]:
        query = (
            db.query(Conversation)
            .options(joinedload(Conversation.messages))
            .filter(Conversation.company_id == company_id)
        )
        if agent_id is not None:
            query = query.filter(Conversation.agent_id == agent_id)
        if channel:
            ch = channel.strip().lower()
            if ch not in INBOX_CHANNELS:
                raise HTTPException(status_code=400, detail=f"Invalid channel '{channel}'")
            query = query.filter(Conversation.channel == ch)
        if status:
            st = status.strip().lower()
            if st not in INBOX_STATUSES:
                raise HTTPException(status_code=400, detail=f"Invalid status '{status}'")
            query = query.filter(Conversation.status == st)
        if assigned_to_user_id is not None:
            query = query.filter(Conversation.assigned_to_user_id == assigned_to_user_id)
        if q and q.strip():
            term = f"%{q.strip()}%"
            query = query.outerjoin(Message).filter(
                or_(
                    Conversation.title.ilike(term),
                    Message.content.ilike(term),
                )
            ).distinct()

        rows = (
            query.order_by(Conversation.updated_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        enriched = [_enrich(c) for c in rows]
        if unread_only:
            enriched = [c for c in enriched if c.unread]
        return enriched

    @staticmethod
    def get_conversation(
        db: Session,
        conversation_id: UUID,
        company_id: UUID,
        *,
        mark_read: bool = False,
    ) -> ConversationDetailResponse:
        conversation = (
            db.query(Conversation)
            .options(joinedload(Conversation.messages))
            .filter(
                Conversation.id == conversation_id,
                Conversation.company_id == company_id,
            )
            .first()
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if mark_read:
            conversation.last_read_at = datetime.now(timezone.utc)
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
        return _detail(conversation)

    @staticmethod
    def create_conversation(db: Session, company_id: UUID, data: ConversationCreate) -> ConversationResponse:
        agent = db.query(AgentConfig).filter(
            AgentConfig.id == data.agent_id,
            AgentConfig.company_id == company_id,
        ).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        channel = (data.channel or "dashboard").strip().lower()
        if channel not in INBOX_CHANNELS:
            raise HTTPException(status_code=400, detail=f"Invalid channel '{data.channel}'")

        conv = Conversation(
            company_id=company_id,
            agent_id=data.agent_id,
            title=data.title,
            channel=channel,
            status="open",
            extra_metadata={},
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return _enrich(conv)

    @staticmethod
    def update_conversation(
        db: Session,
        conversation_id: UUID,
        company_id: UUID,
        data: ConversationUpdate,
    ) -> ConversationResponse:
        conv = (
            db.query(Conversation)
            .options(joinedload(Conversation.messages))
            .filter(
                Conversation.id == conversation_id,
                Conversation.company_id == company_id,
            )
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if data.title is not None:
            conv.title = data.title
        if data.status is not None:
            st = data.status.strip().lower()
            if st not in INBOX_STATUSES:
                raise HTTPException(status_code=400, detail=f"Invalid status '{data.status}'")
            conv.status = st
        if data.clear_assignee:
            conv.assigned_to_user_id = None
        elif data.assigned_to_user_id is not None:
            conv.assigned_to_user_id = data.assigned_to_user_id
        if data.mark_read:
            conv.last_read_at = datetime.now(timezone.utc)

        db.add(conv)
        db.commit()
        db.refresh(conv)
        return _enrich(conv)

    @staticmethod
    def delete_conversation(db: Session, conversation_id: UUID, company_id: UUID):
        conv = (
            db.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
                Conversation.company_id == company_id,
            )
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        db.delete(conv)
        db.commit()

    @staticmethod
    async def send_message(db: Session, conversation_id: UUID, company_id: UUID, content: str) -> dict:
        conv = (
            db.query(Conversation)
            .options(joinedload(Conversation.messages))
            .filter(
                Conversation.id == conversation_id,
                Conversation.company_id == company_id,
            )
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # 1. Save user message
        user_msg = Message(
            conversation_id=conv.id,
            role="user",
            content=content,
        )
        db.add(user_msg)
        conv.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user_msg)

        # 2. Get Agent and resolve knowledge base
        agent = db.query(AgentConfig).filter(AgentConfig.id == conv.agent_id).first()

        provider = agent.web_config.get("provider", "gemini") if agent.web_config else "gemini"
        model = agent.web_config.get("model", "gemini-2.0-flash") if agent.web_config else "gemini-2.0-flash"

        agent_kb = db.query(KnowledgeBaseAgent).filter(KnowledgeBaseAgent.agent_id == agent.id).first()

        system_prompt = agent.system_prompt_template or "You are a helpful assistant."

        if agent_kb:
            sources = KnowledgeService.search_knowledge_base(
                db=db,
                query=content,
                top_k=5,
                company_id=company_id,
                kb_id=agent_kb.knowledge_base_id,
            )
            if sources:
                context_blocks = []
                for i, src in enumerate(sources, start=1):
                    context_blocks.append(f"[{i}] (Source: {src.document_name})\n{src.text}")
                context = "\n\n---\n\n".join(context_blocks)
                system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(context=context) + "\n\nOriginal Instructions: " + (agent.system_prompt_template or "")

        db.refresh(conv)
        messages = [{"role": "system", "content": system_prompt}]
        for msg in conv.messages:
            if msg.role in ["user", "assistant", "system", "tool"]:
                messages.append({"role": msg.role, "content": msg.content})

        chat_request = UnifiedChatRequest(
            company_id=str(company_id),
            agent_id=str(agent.id),
            provider=provider,
            model=model,
            messages=messages,
            temperature=agent.temperature,
            max_tokens=1024,
        )

        try:
            response = await AIGatewayService.process_request(chat_request)
            answer = response.content or ""
        except Exception as e:
            logger.error(f"[Conversation] AI Gateway call failed: {e}", exc_info=True)
            answer = "I encountered an error while generating the answer. Please try again later."

        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=answer,
        )
        db.add(assistant_msg)
        # Operator-sent thread: mark read after their exchange
        conv.last_read_at = datetime.now(timezone.utc)
        conv.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(assistant_msg)

        return {
            "user_message": user_msg,
            "assistant_message": assistant_msg,
        }
