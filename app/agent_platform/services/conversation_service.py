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
from app.agent_platform.conversation_schemas import (
    ConversationCreate,
    ConversationDetailResponse,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
)
logger = logging.getLogger(__name__)


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
    async def send_message(
        db: Session,
        conversation_id: UUID,
        company_id: UUID,
        content: str,
        *,
        as_human: bool = False,
        request_handoff: bool = False,
        actor_user_id: Optional[UUID] = None,
        images: Optional[List[Dict[str, Any]]] = None,
    ) -> dict:
        from app.agent_platform.agent_runtime import (
            AgentRuntime,
            resolve_locale,
            resolve_provider_and_model,
        )

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

        if request_handoff:
            conv.status = "pending_human"
            if actor_user_id:
                conv.assigned_to_user_id = actor_user_id

        # Operator human reply — no AI
        if as_human:
            human_msg = Message(
                conversation_id=conv.id,
                role="human",
                content=content,
            )
            db.add(human_msg)
            conv.status = "human"
            if actor_user_id:
                conv.assigned_to_user_id = actor_user_id
            conv.last_read_at = datetime.now(timezone.utc)
            conv.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(human_msg)
            return {
                "user_message": None,
                "assistant_message": None,
                "human_message": human_msg,
                "status": conv.status,
            }

        # 1. Save user message (dashboard / playground operator asking AI)
        user_msg = Message(
            conversation_id=conv.id,
            role="user",
            content=content,
        )
        db.add(user_msg)
        conv.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user_msg)

        # Skip AI when conversation is with a human
        if (conv.status or "").lower() in {"pending_human", "human"}:
            note = Message(
                conversation_id=conv.id,
                role="assistant",
                content="This conversation is with a human agent. Use Reply as human, or set status back to Open to resume AI.",
            )
            db.add(note)
            db.commit()
            db.refresh(note)
            return {"user_message": user_msg, "assistant_message": note, "status": conv.status}

        # 2. Get Agent and resolve knowledge base
        agent = db.query(AgentConfig).filter(AgentConfig.id == conv.agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        if agent.status == "PAUSED":
            note = Message(
                conversation_id=conv.id,
                role="assistant",
                content="This agent is paused. Resume it from the agent's Overview to continue chatting.",
            )
            db.add(note)
            db.commit()
            db.refresh(note)
            return {"user_message": user_msg, "assistant_message": note, "status": conv.status}

        locale = resolve_locale(metadata=conv.extra_metadata, web_config=agent.web_config)
        provider, model = resolve_provider_and_model(agent)

        db.refresh(conv)

        from app.usage.dimensions import UsageDimension
        from app.usage.service import UsageService

        usage_service = UsageService(db)
        usage_service.check_quota(company_id, UsageDimension.AI_MESSAGES, quantity=1)
        usage_service.check_quota(company_id, UsageDimension.TOTAL_TOKENS, quantity=1)

        usage_ctx = dict(source="dashboard", is_widget=False)
        usage_payload: Dict[str, Any] = {}
        try:
            response, _sources = await AgentRuntime.run_turn(
                db,
                agent=agent,
                company_id=company_id,
                conv_messages=conv.messages,
                user_content=content,
                locale=locale,
                provider=provider,
                model=model,
                temperature=agent.temperature,
                image_blocks=images,
                usage_ctx=usage_ctx,
            )
            answer = response.content or ""
            usage_payload = {
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
                "estimated_cost": response.estimated_cost,
                "provider": response.provider,
                "model": response.model,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[Conversation] AI Gateway call failed: {e}", exc_info=True)
            answer = "I encountered an error while generating the answer. Please try again later."

        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=answer,
        )
        db.add(assistant_msg)
        conv.last_read_at = datetime.now(timezone.utc)
        conv.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(assistant_msg)

        return {
            "user_message": user_msg,
            "assistant_message": assistant_msg,
            "status": conv.status,
            "usage": usage_payload,
        }
