"""
app/agent_platform/knowledge/rag_service.py
RAG (Retrieval-Augmented Generation) service.

Flow:
  User Question
      │
      ▼
  Knowledge Search  (pgvector cosine similarity)
      │
      ▼
  Relevant Chunks   (top-k ranked results)
      │
      ▼
  Prompt Builder    (system prompt + context injection)
      │
      ▼
  AI Gateway        (provider-independent: Ollama / Gemini / OpenAI / Anthropic / OpenRouter)
      │
      ▼
  Answer + Sources

The RAG pipeline is completely provider-independent.  The AI Gateway decides
which LLM to use based on the agent's default_model_id or the request override.
"""
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.agent_platform.knowledge.services import KnowledgeService
from app.agent_platform.knowledge.schemas import SearchResult

logger = logging.getLogger(__name__)

# ── Prompt templates ──────────────────────────────────────────────────────────

_SYSTEM_PROMPT_TEMPLATE = """\
You are a helpful, accurate assistant. Answer the user's question using ONLY \
the context provided below. If the answer is not in the context, say \
"I don't have enough information to answer that."

Context:
{context}
"""

_NO_CONTEXT_SYSTEM_PROMPT = """\
You are a helpful assistant. Answer the user's question as accurately as possible.
"""


class RAGService:
    """
    Orchestrates the full RAG pipeline:
    retrieve → build prompt → call AI Gateway → return answer + sources.
    """

    @staticmethod
    async def query(
        db: Session,
        question: str,
        company_id: UUID,
        kb_id: Optional[UUID] = None,
        agent_id: Optional[UUID] = None,
        provider: str = "gemini",
        model: str = "gemini-2.0-flash",
        top_k: int = 5,
    ) -> dict:
        """
        Run the full RAG pipeline for a user question.

        Args:
            db:          Database session.
            question:    The user's natural-language question.
            company_id:  Tenant isolation key.
            kb_id:       Restrict retrieval to one knowledge base (optional).
            agent_id:    Agent to attribute the request to (for usage logging).
            provider:    LLM provider name (gemini / openai / anthropic / ollama / openrouter).
            model:       Model name to use for generation.
            top_k:       Number of chunks to retrieve.

        Returns:
            {
              "answer":  str,
              "sources": List[SearchResult],
              "provider": str,
              "model": str,
            }
        """
        # ── Step 1: Retrieve relevant chunks ─────────────────────────────────
        sources: List[SearchResult] = KnowledgeService.search_knowledge_base(
            db=db,
            query=question,
            top_k=top_k,
            company_id=company_id,
            kb_id=kb_id,
        )

        # ── Step 2: Build system prompt ───────────────────────────────────────
        if sources:
            context_blocks = []
            for i, src in enumerate(sources, start=1):
                context_blocks.append(
                    f"[{i}] (Source: {src.document_name})\n{src.text}"
                )
            context = "\n\n---\n\n".join(context_blocks)
            system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(context=context)
        else:
            logger.info(
                f"[RAG] No relevant chunks found for company={company_id}, "
                f"answering without context."
            )
            system_prompt = _NO_CONTEXT_SYSTEM_PROMPT

        # ── Step 3: Call AI Gateway ───────────────────────────────────────────
        try:
            from app.agent_platform.schemas import UnifiedChatRequest
            from app.agent_platform.gateway.service import AIGatewayService

            chat_request = UnifiedChatRequest(
                company_id=str(company_id),
                agent_id=str(agent_id) if agent_id else None,
                provider=provider,
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                temperature=0.3,   # lower temp for factual RAG responses
                max_tokens=1024,
            )

            response = await AIGatewayService.process_request(chat_request)
            answer = response.content or ""

        except Exception as e:
            logger.error(f"[RAG] AI Gateway call failed: {e}", exc_info=True)
            answer = (
                "I encountered an error while generating the answer. "
                "Please try again later."
            )

        logger.info(
            f"[RAG] Query complete: company={company_id} "
            f"chunks={len(sources)} provider={provider} model={model}"
        )

        return {
            "answer": answer,
            "sources": sources,
            "provider": provider,
            "model": model,
        }
