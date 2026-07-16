"""
app/ai/service.py

Business logic for the AI Gateway.
"""
import uuid
import time
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.config.settings import settings
from app.ai.repository import AIRepository
from app.ai.providers.factory import AIProviderFactory
from app.ai.schema import ChatRequest, GenerateRequest, ChatResponse, GenerateResponse
from app.ai.model import AIRequestStatus
from app.companies.model import Company

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
        
        provider_name = payload.provider or settings.AI_PROVIDER
        provider = AIProviderFactory.get_provider(provider_name)
        
        request_meta = {
            "temperature": payload.temperature,
            "max_tokens": payload.max_tokens,
            "conversation_id": payload.conversation_id
        }
        
        messages_dict = [m.model_dump() for m in payload.messages]
        prompt_length = sum(len(m.content) for m in payload.messages)
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
            prompt=messages_dict,
            request_metadata=request_meta
        )

        start_time = time.time()
        try:
            ai_response = await provider.chat(messages=messages_dict, model=payload.model, temperature=payload.temperature, max_tokens=payload.max_tokens)
            
            latency_ms = (time.time() - start_time) * 1000
            actual_cost = self._calculate_estimated_cost(ai_response.model_used, ai_response.input_tokens, ai_response.output_tokens)
            
            # Reconcile cost
            company = self.db.query(Company).filter(Company.id == company_id).with_for_update().first()
            company.credits_balance = float(company.credits_balance) + (upfront_cost - actual_cost)
            self.db.commit()
            
            # Log success
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
            
            return ChatResponse(
                content=ai_response.content,
                input_tokens=ai_response.input_tokens,
                output_tokens=ai_response.output_tokens,
                model_used=ai_response.model_used,
                estimated_cost=actual_cost,
                currency="USD",
                conversation_id=payload.conversation_id or uuid.uuid4().hex
            )
            
        except Exception as e:
            logger.error(f"AI Chat failed: {str(e)}")
            
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
