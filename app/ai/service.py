"""
app/ai/service.py

Business logic for the AI Gateway.
"""
import uuid
import time
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.ai.gateway_workspace import (
    KNOWN_PROVIDERS,
    get_or_create_workspace_settings,
)
from app.config.settings import settings
from app.ai.repository import AIRepository
from app.ai.providers.factory import AIProviderFactory
from app.ai.schema import ChatRequest, GenerateRequest, ChatResponse, GenerateResponse
from app.ai.model import AIRequestStatus
from app.companies.model import Company
from app.openai_compat.policies.retry import RetryPolicy, with_retry
from app.openai_compat.providers.metrics import get_routing_metrics
from app.openai_compat.tools import normalize_tool_choice, normalize_tools
from app.openai_compat.vision import flatten_text

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AIRepository(db)

    def _check_rate_limits(self, company_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """
        Rate Limit Ready:
        Implementation नहीं, लेकिन structure रखो:
        company_limit, daily_limit, monthly_limit
        """
        # Placeholder for Rate Limiting
        # e.g., if cache.get(f"rate_limit:{company_id}") > max_limit: raise HTTP 429
        pass

    def _calculate_estimated_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """
        Placeholder cost calculation.
        In a real scenario, fetch pricing table.
        """
        # Placeholder: $0.0001 per 1k input, $0.0002 per 1k output
        return (input_tokens / 1000.0 * 0.0001) + (output_tokens / 1000.0 * 0.0002)

    def _estimate_upfront_cost(self, model: str, prompt_length: int, max_tokens: int) -> float:
        max_input = max(prompt_length / 4, 10)
        return self._calculate_estimated_cost(model, max_input, max_tokens)

    async def chat(self, company_id: uuid.UUID, user_id: uuid.UUID, payload: ChatRequest) -> ChatResponse:
        self._check_rate_limits(company_id, user_id)

        ws = get_or_create_workspace_settings(self.db, company_id)
        allowed = [p.lower() for p in (ws.allowed_providers or KNOWN_PROVIDERS)]
        provider_name = (payload.provider or ws.default_provider or settings.AI_PROVIDER or "openai").lower()
        if provider_name not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{provider_name}' is not allowed for this workspace",
            )

        request_meta = {
            "temperature": payload.temperature,
            "max_tokens": payload.max_tokens,
            "conversation_id": payload.conversation_id,
            "tools": bool(payload.tools),
            "rag_query": payload.rag_query,
        }

        messages_dict = [m.model_dump(exclude_none=True) for m in payload.messages]
        if payload.rag_query:
            # Additive RAG hook — prepend context placeholder when knowledge service unavailable
            rag_context = await self._maybe_rag_context(
                company_id, payload.rag_query, payload.knowledge_base_id
            )
            if rag_context:
                messages_dict = [
                    {"role": "system", "content": f"Knowledge context:\n{rag_context}"},
                    *messages_dict,
                ]

        prompt_length = sum(len(flatten_text(m.get("content"))) for m in messages_dict)
        max_tokens = payload.max_tokens or 1000
        upfront_cost = self._estimate_upfront_cost(payload.model, prompt_length, max_tokens)

        company = self.db.query(Company).filter(Company.id == company_id).with_for_update().first()
        if not company or float(company.credits_balance) < upfront_cost:
            raise HTTPException(status_code=402, detail="Insufficient credits for AI Request")

        company.credits_balance = float(company.credits_balance) - upfront_cost
        self.db.commit()

        db_request = self.repo.create_request(
            company_id=company_id,
            user_id=user_id,
            app_id=payload.app_id,
            provider=provider_name,
            model=payload.model,
            prompt=messages_dict,
            request_metadata=request_meta,
        )

        tools = normalize_tools(payload.tools)
        tool_choice = normalize_tool_choice(payload.tool_choice)
        fallback_order = [provider_name]
        if payload.enable_fallback:
            for p in allowed:
                if p not in fallback_order:
                    fallback_order.append(p)

        policy = RetryPolicy(
            max_attempts=max(1, int(ws.retry_max_attempts or 1)),
            backoff_ms=int(getattr(settings, "GATEWAY_RETRY_BACKOFF_MS", 200) or 0),
            timeout_seconds=float(ws.timeout_seconds or 60.0),
        )

        start_time = time.time()
        last_error: Optional[Exception] = None
        ai_response = None
        used_provider = provider_name

        try:
            for cand in fallback_order:
                used_provider = cand
                provider = AIProviderFactory.get_provider(cand)

                async def _call(p=provider, name=cand):
                    return await p.chat(
                        messages=messages_dict,
                        model=payload.model,
                        temperature=payload.temperature,
                        max_tokens=payload.max_tokens,
                        tools=tools or None,
                        tool_choice=tool_choice,
                    )

                try:
                    t0 = time.time()
                    ai_response = await with_retry(_call, policy=policy)
                    latency_ms = (time.time() - t0) * 1000
                    get_routing_metrics().record_selection(
                        cand, policy=ws.routing_policy or "default", routing_time_ms=0.0
                    )
                    get_routing_metrics().record_latency(cand, latency_ms)
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    get_routing_metrics().record_error(cand)
                    logger.warning("AI chat provider %s failed: %s", cand, exc)
                    if not payload.enable_fallback:
                        break
                    continue

            if ai_response is None:
                raise last_error or RuntimeError("All providers failed")

            latency_ms = (time.time() - start_time) * 1000
            actual_cost = self._calculate_estimated_cost(
                ai_response.model_used, ai_response.input_tokens, ai_response.output_tokens
            )

            company = self.db.query(Company).filter(Company.id == company_id).with_for_update().first()
            company.credits_balance = float(company.credits_balance) + (upfront_cost - actual_cost)
            self.db.commit()

            self.repo.update_request(
                request_id=db_request.id,
                response={"content": ai_response.content},
                tokens_input=ai_response.input_tokens,
                tokens_output=ai_response.output_tokens,
                latency=latency_ms,
                estimated_cost=actual_cost,
                status=AIRequestStatus.SUCCESS,
                additional_metadata={
                    "provider_response_id": ai_response.provider_response_id,
                    "provider_used": used_provider,
                },
            )

            try:
                from app.usage.service import UsageService

                UsageService(self.db).record_ai_usage(
                    company_id,
                    prompt_tokens=int(ai_response.input_tokens or 0),
                    completion_tokens=int(ai_response.output_tokens or 0),
                    source="ai_gateway",
                    estimated_cost=float(actual_cost or 0),
                    provider=used_provider,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("usage meter update after chat failed: %s", exc)

            return ChatResponse(
                content=ai_response.content,
                input_tokens=ai_response.input_tokens,
                output_tokens=ai_response.output_tokens,
                model_used=ai_response.model_used,
                estimated_cost=actual_cost,
                currency="USD",
                conversation_id=payload.conversation_id or uuid.uuid4().hex,
            )

        except Exception as e:
            logger.error(f"AI Chat failed: {str(e)}")

            company = self.db.query(Company).filter(Company.id == company_id).with_for_update().first()
            if company:
                company.credits_balance = float(company.credits_balance) + upfront_cost
                self.db.commit()

            latency_ms = (time.time() - start_time) * 1000
            self.repo.update_request(
                request_id=db_request.id,
                status=AIRequestStatus.FAILED,
                latency=latency_ms,
                estimated_cost=0.0,
                additional_metadata={"error": str(e)},
            )
            raise HTTPException(status_code=500, detail="AI Provider Error")

    async def _maybe_rag_context(
        self,
        company_id: uuid.UUID,
        query: str,
        knowledge_base_id: Optional[uuid.UUID],
    ) -> Optional[str]:
        """Best-effort RAG context; never breaks chat if knowledge stack is unavailable."""
        try:
            from app.agent_platform.knowledge.rag_service import RagService

            rag = RagService(self.db)
            if hasattr(rag, "retrieve"):
                hits = await rag.retrieve(  # type: ignore[misc]
                    company_id=company_id,
                    query=query,
                    knowledge_base_id=knowledge_base_id,
                    limit=3,
                )
                if isinstance(hits, list) and hits:
                    parts = []
                    for h in hits[:3]:
                        if isinstance(h, dict):
                            parts.append(str(h.get("text") or h.get("content") or ""))
                        else:
                            parts.append(str(h))
                    text = "\n---\n".join(p for p in parts if p)
                    return text or None
        except Exception:  # noqa: BLE001
            logger.debug("RAG context unavailable", exc_info=True)
        return None

    async def generate(self, company_id: uuid.UUID, user_id: uuid.UUID, payload: GenerateRequest) -> GenerateResponse:
        self._check_rate_limits(company_id, user_id)
        
        provider_name = payload.provider or settings.AI_PROVIDER
        provider = AIProviderFactory.get_provider(provider_name)
        
        request_meta = {
            "temperature": payload.temperature,
            "max_tokens": payload.max_tokens
        }
        
        prompt_length = len(payload.prompt)
        max_tokens = payload.max_tokens or 1000
        upfront_cost = self._estimate_upfront_cost(payload.model, prompt_length, max_tokens)
        
        # Deduct upfront cost
        company = self.db.query(Company).filter(Company.id == company_id).with_for_update().first()
        if not company or float(company.credits_balance) < upfront_cost:
            raise HTTPException(status_code=402, detail="Insufficient credits for AI Request")
        
        company.credits_balance = float(company.credits_balance) - upfront_cost
        self.db.commit()
        
        db_request = self.repo.create_request(
            company_id=company_id,
            user_id=user_id,
            app_id=payload.app_id,
            provider=provider_name,
            model=payload.model,
            prompt={"text": payload.prompt},
            request_metadata=request_meta
        )

        start_time = time.time()
        try:
            ai_response = await provider.generate(prompt=payload.prompt, model=payload.model, temperature=payload.temperature, max_tokens=payload.max_tokens)
            
            latency_ms = (time.time() - start_time) * 1000
            actual_cost = self._calculate_estimated_cost(ai_response.model_used, ai_response.input_tokens, ai_response.output_tokens)
            
            # Reconcile cost
            company = self.db.query(Company).filter(Company.id == company_id).with_for_update().first()
            company.credits_balance = float(company.credits_balance) + (upfront_cost - actual_cost)
            self.db.commit()
            
            self.repo.update_request(
                request_id=db_request.id,
                response={"content": ai_response.content},
                tokens_input=ai_response.input_tokens,
                tokens_output=ai_response.output_tokens,
                latency=latency_ms,
                estimated_cost=actual_cost,
                status=AIRequestStatus.SUCCESS,
                additional_metadata={"provider_response_id": ai_response.provider_response_id}
            )
            
            return GenerateResponse(
                content=ai_response.content,
                input_tokens=ai_response.input_tokens,
                output_tokens=ai_response.output_tokens,
                model_used=ai_response.model_used,
                estimated_cost=actual_cost,
                currency="USD"
            )
            
        except Exception as e:
            logger.error(f"AI Generate failed: {str(e)}")
            
            # Refund upfront cost on failure
            company = self.db.query(Company).filter(Company.id == company_id).with_for_update().first()
            if company:
                company.credits_balance = float(company.credits_balance) + upfront_cost
                self.db.commit()
                
            latency_ms = (time.time() - start_time) * 1000
            self.repo.update_request(
                request_id=db_request.id,
                status=AIRequestStatus.FAILED,
                latency=latency_ms,
                estimated_cost=0.0,
                additional_metadata={"error": str(e)}
            )
            raise HTTPException(status_code=500, detail="AI Provider Error")

    def get_history(self, company_id: uuid.UUID, user_id: uuid.UUID, page: int = 1, page_size: int = 20):
        skip = (page - 1) * page_size
        return self.repo.get_history(company_id=company_id, user_id=user_id, skip=skip, limit=page_size)

    def delete_history(self, company_id: uuid.UUID, request_id: uuid.UUID) -> None:
        if not self.repo.soft_delete(request_id, company_id):
            raise HTTPException(status_code=404, detail="Request history not found")

    async def get_health(self) -> Dict[str, str]:
        """Check all providers configuration/health."""
        providers = ["openai", "gemini", "anthropic", "ollama", "openrouter"]
        health_status = {}
        for p in providers:
            try:
                provider_instance = AIProviderFactory.get_provider(p)
                is_healthy = await provider_instance.health()
                health_status[p] = "configured" if is_healthy else "unconfigured"
            except Exception:
                health_status[p] = "error"
        return health_status
