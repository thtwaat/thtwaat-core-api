"""
app/ai/repository.py

Database operations for AI Requests.
"""
import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from datetime import datetime, timezone
from app.ai.model import AIRequest, AIRequestStatus

class AIRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_request(
        self,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        provider: str,
        model: str,
        prompt: Any,
        request_metadata: Optional[Dict[str, Any]] = None,
        app_id: Optional[uuid.UUID] = None
    ) -> AIRequest:
        db_request = AIRequest(
            company_id=company_id,
            user_id=user_id,
            app_id=app_id,
            provider=provider,
            model=model,
            prompt=prompt,
            request_metadata=request_metadata or {}
        )
        self.db.add(db_request)
        self.db.commit()
        self.db.refresh(db_request)
        return db_request

    def update_request(
        self,
        request_id: uuid.UUID,
        response: Any = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
        latency: float = 0.0,
        estimated_cost: float = 0.0,
        status: AIRequestStatus = AIRequestStatus.SUCCESS,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        db_request = self.db.execute(select(AIRequest).where(AIRequest.id == request_id)).scalar_one_or_none()
        if not db_request:
            return
            
        db_request.response = response
        db_request.tokens_input = tokens_input
        db_request.tokens_output = tokens_output
        db_request.latency = latency
        db_request.estimated_cost = estimated_cost
        db_request.status = status
        
        if additional_metadata:
            current_meta = dict(db_request.request_metadata or {})
            current_meta.update(additional_metadata)
            db_request.request_metadata = current_meta
            
        self.db.commit()

    def get_history(self, company_id: uuid.UUID, user_id: uuid.UUID, skip: int = 0, limit: int = 20) -> List[AIRequest]:
        stmt = select(AIRequest).where(
            AIRequest.company_id == company_id,
            AIRequest.user_id == user_id,
            AIRequest.deleted_at.is_(None)
        ).order_by(AIRequest.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def soft_delete(self, request_id: uuid.UUID, company_id: uuid.UUID) -> bool:
        db_request = self.db.execute(select(AIRequest).where(
            AIRequest.id == request_id, 
            AIRequest.company_id == company_id
        )).scalar_one_or_none()
        
        if db_request:
            db_request.deleted_at = datetime.now(timezone.utc)
            self.db.commit()
            return True
        return False
