"""Repository layer for agent publish + API keys."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.models.api_key import AgentApiKey


class PublishRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_agent_for_company(
        self, agent_id: UUID, company_id: UUID, *, include_deleted: bool = False
    ) -> Optional[AgentConfig]:
        q = self.db.query(AgentConfig).filter(
            AgentConfig.id == agent_id, AgentConfig.company_id == company_id
        )
        if not include_deleted:
            q = q.filter(AgentConfig.deleted_at.is_(None))
        return q.first()

    def get_agent(self, agent_id: UUID, *, include_deleted: bool = False) -> Optional[AgentConfig]:
        q = self.db.query(AgentConfig).filter(AgentConfig.id == agent_id)
        if not include_deleted:
            q = q.filter(AgentConfig.deleted_at.is_(None))
        return q.first()

    def get_agent_by_widget_id(self, widget_id: str) -> Optional[AgentConfig]:
        return (
            self.db.query(AgentConfig)
            .filter(
                AgentConfig.widget_id == widget_id,
                AgentConfig.deleted_at.is_(None),
            )
            .first()
        )

    def save_agent(self, agent: AgentConfig) -> AgentConfig:
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def get_active_key_for_agent(self, agent_id: UUID, company_id: UUID) -> Optional[AgentApiKey]:
        return (
            self.db.query(AgentApiKey)
            .filter(
                AgentApiKey.agent_id == agent_id,
                AgentApiKey.company_id == company_id,
                AgentApiKey.is_active.is_(True),
                AgentApiKey.revoked_at.is_(None),
            )
            .order_by(AgentApiKey.created_at.desc())
            .first()
        )

    def list_keys(self, agent_id: UUID, company_id: UUID) -> List[AgentApiKey]:
        return (
            self.db.query(AgentApiKey)
            .filter(AgentApiKey.agent_id == agent_id, AgentApiKey.company_id == company_id)
            .order_by(AgentApiKey.created_at.desc())
            .all()
        )

    def get_key(self, key_id: UUID, agent_id: UUID, company_id: UUID) -> Optional[AgentApiKey]:
        return (
            self.db.query(AgentApiKey)
            .filter(
                AgentApiKey.id == key_id,
                AgentApiKey.agent_id == agent_id,
                AgentApiKey.company_id == company_id,
            )
            .first()
        )

    def get_key_by_hash(self, key_hash: str) -> Optional[AgentApiKey]:
        return (
            self.db.query(AgentApiKey)
            .filter(AgentApiKey.key_hash == key_hash, AgentApiKey.is_active.is_(True))
            .first()
        )

    def create_key(self, api_key: AgentApiKey) -> AgentApiKey:
        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key

    def revoke_key(self, api_key: AgentApiKey) -> AgentApiKey:
        api_key.is_active = False
        api_key.revoked_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key

    def delete_key(self, api_key: AgentApiKey) -> None:
        self.db.delete(api_key)
        self.db.commit()

    def touch_last_used(self, api_key: AgentApiKey) -> None:
        api_key.last_used_at = datetime.now(timezone.utc)
        self.db.commit()
