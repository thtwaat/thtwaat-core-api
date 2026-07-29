import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.agent_platform.models.conversation import Conversation, Message
from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.knowledge.models.knowledge_base import KnowledgeBaseAgent
from app.agent_platform.conversation_schemas import ConversationCreate
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

class ConversationService:

    @staticmethod
    def get_conversations(db: Session, company_id: UUID, skip: int = 0, limit: int = 50) -> List[Conversation]:
        return db.query(Conversation).filter(Conversation.company_id == company_id).order_by(Conversation.created_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def get_conversation(db: Session, conversation_id: UUID, company_id: UUID) -> Conversation:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.company_id == company_id
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation

    @staticmethod
    def create_conversation(db: Session, company_id: UUID, data: ConversationCreate) -> Conversation:
        agent = db.query(AgentConfig).filter(
            AgentConfig.id == data.agent_id,
            AgentConfig.company_id == company_id
        ).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
            
        conv = Conversation(
            company_id=company_id,
            agent_id=data.agent_id,
            title=data.title
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv

    @staticmethod
    def delete_conversation(db: Session, conversation_id: UUID, company_id: UUID):
        conv = ConversationService.get_conversation(db, conversation_id, company_id)
        db.delete(conv)
        db.commit()

    @staticmethod
    async def send_message(db: Session, conversation_id: UUID, company_id: UUID, content: str) -> dict:
        conv = ConversationService.get_conversation(db, conversation_id, company_id)
        
        # 1. Save user message
        user_msg = Message(
            conversation_id=conv.id,
            role="user",
            content=content
        )
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)
        
        # 2. Get Agent and resolve knowledge base
        agent = db.query(AgentConfig).filter(AgentConfig.id == conv.agent_id).first()
        
        # Determine provider and model (Default to agent's config or global defaults)
        provider = agent.web_config.get("provider", "gemini") if agent.web_config else "gemini"
        model = agent.web_config.get("model", "gemini-2.0-flash") if agent.web_config else "gemini-2.0-flash"
        
        # Check if agent has KB attached
        agent_kb = db.query(KnowledgeBaseAgent).filter(KnowledgeBaseAgent.agent_id == agent.id).first()
        
        system_prompt = agent.system_prompt_template or "You are a helpful assistant."
        sources = []
        
        if agent_kb:
            # 3. Retrieve RAG Context
            sources = KnowledgeService.search_knowledge_base(
                db=db,
                query=content,
                top_k=5,
                company_id=company_id,
                kb_id=agent_kb.knowledge_base_id
            )
            if sources:
                context_blocks = []
                for i, src in enumerate(sources, start=1):
                    context_blocks.append(f"[{i}] (Source: {src.document_name})\n{src.text}")
                context = "\n\n---\n\n".join(context_blocks)
                system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(context=context) + "\n\nOriginal Instructions: " + (agent.system_prompt_template or "")
        
        # 4. Build message history
        # Reload conv.messages to include the new user message
        db.refresh(conv)
        messages = [{"role": "system", "content": system_prompt}]
        for msg in conv.messages:
            if msg.role in ["user", "assistant", "system", "tool"]:
                messages.append({"role": msg.role, "content": msg.content})
            
        # 5. Call Universal AI Gateway
        chat_request = UnifiedChatRequest(
            company_id=str(company_id),
            agent_id=str(agent.id),
            provider=provider,
            model=model,
            messages=messages,
            temperature=agent.temperature,
            max_tokens=1024
        )
        
        try:
            response = await AIGatewayService.process_request(chat_request)
            answer = response.content or ""
        except Exception as e:
            logger.error(f"[Conversation] AI Gateway call failed: {e}", exc_info=True)
            answer = "I encountered an error while generating the answer. Please try again later."
            
        # 6. Save Assistant response
        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=answer
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)
        
        return {
            "user_message": user_msg,
            "assistant_message": assistant_msg
        }
