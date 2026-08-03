"""Repository for openai_completion_logs."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.openai_compat.models import OpenAICompletionLog


class CompletionLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, row: OpenAICompletionLog) -> OpenAICompletionLog:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_by_completion_id(self, completion_id: str) -> Optional[OpenAICompletionLog]:
        return (
            self.db.query(OpenAICompletionLog)
            .filter(OpenAICompletionLog.completion_id == completion_id)
            .first()
        )

    def list_for_company(self, company_id: UUID, *, limit: int = 50) -> list[OpenAICompletionLog]:
        return (
            self.db.query(OpenAICompletionLog)
            .filter(OpenAICompletionLog.company_id == company_id)
            .order_by(OpenAICompletionLog.created_at.desc())
            .limit(limit)
            .all()
        )
