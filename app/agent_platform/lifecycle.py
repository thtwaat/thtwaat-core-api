"""Production-grade agent soft delete, cleanup, and restore."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.models.api_key import AgentApiKey
from app.agent_platform.models.conversation import Conversation, Message
from app.agent_platform.knowledge.models.knowledge_base import KnowledgeBaseAgent
from app.enterprise.models import AuditSeverity
from app.enterprise.service import EnterpriseService

logger = logging.getLogger(__name__)

RETENTION_DAYS = 30
STATUS_DELETED = "DELETED"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AgentLifecycleService:
    """Soft-delete agents, queue cleanup, restore within retention, permanent purge."""

    def __init__(self, db: Session):
        self.db = db

    # ── lookups ───────────────────────────────────────────────────────────────

    def get_active(
        self, agent_id: UUID, company_id: Optional[UUID] = None
    ) -> Optional[AgentConfig]:
        q = self.db.query(AgentConfig).filter(
            AgentConfig.id == agent_id,
            AgentConfig.deleted_at.is_(None),
        )
        if company_id is not None:
            q = q.filter(AgentConfig.company_id == company_id)
        return q.first()

    def get_including_deleted(
        self, agent_id: UUID, company_id: Optional[UUID] = None
    ) -> Optional[AgentConfig]:
        q = self.db.query(AgentConfig).filter(AgentConfig.id == agent_id)
        if company_id is not None:
            q = q.filter(AgentConfig.company_id == company_id)
        return q.first()

    def active_filter(self):
        return AgentConfig.deleted_at.is_(None)

    # ── impact preview ────────────────────────────────────────────────────────

    def delete_impact(self, agent: AgentConfig) -> Dict[str, Any]:
        api_keys = (
            self.db.query(AgentApiKey)
            .filter(AgentApiKey.agent_id == agent.id)
            .count()
        )
        conversations = (
            self.db.query(Conversation)
            .filter(Conversation.agent_id == agent.id)
            .count()
        )
        kb_links = (
            self.db.query(KnowledgeBaseAgent)
            .filter(KnowledgeBaseAgent.agent_id == agent.id)
            .count()
        )
        web = agent.web_config or {}
        draft_prompts = web.get("suggested_prompts") or web.get("draft_prompts") or []
        scheduled_jobs = int(web.get("scheduled_jobs_count") or 0)
        return {
            "agent_id": str(agent.id),
            "name": agent.name,
            "published": agent.status == "PUBLISHED" or agent.published_at is not None,
            "status": agent.status,
            "widget": bool(agent.widget_id),
            "widget_id": agent.widget_id,
            "api_keys": api_keys,
            "playground": True,
            "draft_prompts": len(draft_prompts) if isinstance(draft_prompts, list) else int(bool(draft_prompts)),
            "scheduled_jobs": scheduled_jobs,
            "conversations": conversations,
            "knowledge_attachments": kb_links,
            "retention_days": RETENTION_DAYS,
        }

    # ── soft delete ───────────────────────────────────────────────────────────

    def soft_delete(
        self,
        *,
        agent_id: UUID,
        company_id: UUID,
        user_id: UUID,
        keep_conversations: bool = True,
        keep_knowledge: bool = True,
        reason: Optional[str] = None,
        confirm_unpublish: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AgentConfig:
        agent = self.get_active(agent_id, company_id)
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        was_published = agent.status == "PUBLISHED" or agent.published_at is not None
        if was_published and not confirm_unpublish:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "agent_published",
                    "message": (
                        "This agent is currently published. "
                        "It will be unpublished before deletion."
                    ),
                    "require_confirm_unpublish": True,
                },
            )

        before = {
            "status": agent.status,
            "published_at": agent.published_at.isoformat() if agent.published_at else None,
            "widget_id": agent.widget_id,
        }

        # Unpublish first (reuse publish semantics without a second delete path).
        if was_published:
            agent.status = "DRAFT"
            agent.published_at = None
            self._revoke_all_keys(agent.id, company_id, commit=False)

        options = {
            "keep_conversations": keep_conversations,
            "keep_knowledge": keep_knowledge,
            "delete_conversations": not keep_conversations,
            "delete_linked_knowledge": not keep_knowledge,
            "was_published": was_published,
        }

        agent.status = STATUS_DELETED
        agent.deleted_at = _now()
        agent.deleted_by = user_id
        agent.delete_reason = (reason or "").strip() or None
        agent.delete_options = options
        self.db.add(agent)
        self.db.flush()

        EnterpriseService(self.db).audit(
            company_id,
            user_id,
            action="agent.soft_delete",
            resource_type="agent",
            resource_id=str(agent.id),
            severity=AuditSeverity.WARNING,
            before=before,
            after={
                "status": agent.status,
                "deleted_at": agent.deleted_at.isoformat(),
                "delete_options": options,
            },
            metadata={
                "workspace_id": str(company_id),
                "reason": agent.delete_reason,
                "retention_days": RETENTION_DAYS,
            },
            ip_address=ip_address,
            user_agent=user_agent,
            commit=False,
        )
        self.db.commit()
        self.db.refresh(agent)

        self._enqueue_cleanup(agent.id, company_id)
        return agent

    # ── restore (super admin) ─────────────────────────────────────────────────

    def restore(
        self,
        *,
        agent_id: UUID,
        actor_user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> AgentConfig:
        agent = self.get_including_deleted(agent_id)
        if not agent or agent.deleted_at is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deleted agent not found",
            )

        age = _now() - (
            agent.deleted_at
            if agent.deleted_at.tzinfo
            else agent.deleted_at.replace(tzinfo=timezone.utc)
        )
        if age > timedelta(days=RETENTION_DAYS):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail=f"Retention period of {RETENTION_DAYS} days has expired",
            )

        before = {
            "status": agent.status,
            "deleted_at": agent.deleted_at.isoformat(),
            "deleted_by": str(agent.deleted_by) if agent.deleted_by else None,
        }
        agent.status = "DRAFT"
        agent.deleted_at = None
        agent.deleted_by = None
        agent.delete_reason = None
        # Keep delete_options for forensic trail unless cleared
        self.db.add(agent)
        self.db.flush()

        EnterpriseService(self.db).audit(
            agent.company_id,
            actor_user_id,
            action="agent.restore",
            resource_type="agent",
            resource_id=str(agent.id),
            severity=AuditSeverity.INFO,
            before=before,
            after={"status": agent.status, "deleted_at": None},
            metadata={
                "workspace_id": str(agent.company_id),
                "reason": reason,
            },
            ip_address=ip_address,
            user_agent=user_agent,
            commit=False,
        )
        self.db.commit()
        self.db.refresh(agent)
        return agent

    # ── cleanup (queued after soft delete) ────────────────────────────────────

    def run_cleanup(self, agent_id: UUID) -> Dict[str, Any]:
        agent = self.get_including_deleted(agent_id)
        if not agent or agent.deleted_at is None:
            return {"ok": False, "reason": "not_soft_deleted"}

        options = agent.delete_options or {}
        result: Dict[str, Any] = {
            "agent_id": str(agent_id),
            "revoked_keys": 0,
            "deleted_conversations": 0,
            "detached_knowledge": 0,
            "cleared_caches": False,
        }

        # Always revoke keys on cleanup (widget / API no longer usable).
        result["revoked_keys"] = self._revoke_all_keys(
            agent.id, agent.company_id, commit=False
        )

        if options.get("delete_conversations") or not options.get("keep_conversations", True):
            conv_ids = [
                row.id
                for row in self.db.query(Conversation.id)
                .filter(Conversation.agent_id == agent.id)
                .all()
            ]
            if conv_ids:
                self.db.query(Message).filter(Message.conversation_id.in_(conv_ids)).delete(
                    synchronize_session=False
                )
                deleted = (
                    self.db.query(Conversation)
                    .filter(Conversation.agent_id == agent.id)
                    .delete(synchronize_session=False)
                )
                result["deleted_conversations"] = deleted

        # Never delete shared knowledge bases — only detach agent links when requested.
        if options.get("delete_linked_knowledge") or not options.get("keep_knowledge", True):
            detached = (
                self.db.query(KnowledgeBaseAgent)
                .filter(KnowledgeBaseAgent.agent_id == agent.id)
                .delete(synchronize_session=False)
            )
            result["detached_knowledge"] = detached

        result["cleared_caches"] = self._clear_agent_caches(agent)
        self.db.commit()

        EnterpriseService(self.db).audit(
            agent.company_id,
            agent.deleted_by,
            action="agent.cleanup",
            resource_type="agent",
            resource_id=str(agent.id),
            severity=AuditSeverity.INFO,
            after=result,
            metadata={"workspace_id": str(agent.company_id)},
            commit=True,
        )
        logger.info("agent_cleanup_complete %s", result)
        return {"ok": True, **result}

    # ── permanent purge after retention ───────────────────────────────────────

    def purge_expired(self, retention_days: int = RETENTION_DAYS) -> Dict[str, Any]:
        cutoff = _now() - timedelta(days=retention_days)
        expired: List[AgentConfig] = (
            self.db.query(AgentConfig)
            .filter(
                AgentConfig.deleted_at.isnot(None),
                AgentConfig.deleted_at < cutoff,
            )
            .all()
        )
        purged: List[str] = []
        for agent in expired:
            agent_id = str(agent.id)
            company_id = agent.company_id
            # Final cleanup pass then hard delete (CASCADE keys/conversations/attachments).
            # Usage logs keep historical analytics via ON DELETE SET NULL.
            self.run_cleanup(agent.id)
            agent = self.get_including_deleted(UUID(agent_id))
            if not agent:
                purged.append(agent_id)
                continue
            self._clear_agent_caches(agent)
            # Free unique widget_id before hard delete
            agent.widget_id = None
            self.db.add(agent)
            self.db.flush()
            self.db.delete(agent)
            self.db.flush()
            EnterpriseService(self.db).audit(
                company_id,
                None,
                action="agent.permanent_delete",
                resource_type="agent",
                resource_id=agent_id,
                severity=AuditSeverity.CRITICAL,
                metadata={
                    "workspace_id": str(company_id),
                    "retention_days": retention_days,
                },
                commit=False,
            )
            purged.append(agent_id)

        self.db.commit()
        logger.info("agent_purge_expired count=%s", len(purged))
        return {"purged": purged, "count": len(purged)}

    # ── helpers ───────────────────────────────────────────────────────────────

    def _revoke_all_keys(
        self, agent_id: UUID, company_id: UUID, *, commit: bool = True
    ) -> int:
        keys = (
            self.db.query(AgentApiKey)
            .filter(
                AgentApiKey.agent_id == agent_id,
                AgentApiKey.company_id == company_id,
                AgentApiKey.revoked_at.is_(None),
            )
            .all()
        )
        now = _now()
        for key in keys:
            key.is_active = False
            key.revoked_at = now
            self.db.add(key)
        if commit:
            self.db.commit()
        return len(keys)

    def _clear_agent_caches(self, agent: AgentConfig) -> bool:
        """Best-effort clear of playground / embeddings / search caches for this agent."""
        try:
            from app.config.settings import settings
            import redis

            r = redis.from_url(
                f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
                decode_responses=True,
            )
            patterns = [
                f"thtwaat:playground:{agent.id}:*",
                f"thtwaat:agent:{agent.id}:*",
                f"thtwaat:embeddings:agent:{agent.id}:*",
                f"thtwaat:search:agent:{agent.id}:*",
            ]
            if agent.widget_id:
                patterns.append(f"thtwaat:widget:{agent.widget_id}:*")
            deleted = 0
            for pattern in patterns:
                cursor = 0
                while True:
                    cursor, keys = r.scan(cursor=cursor, match=pattern, count=100)
                    if keys:
                        deleted += int(r.delete(*keys))
                    if cursor == 0:
                        break
            logger.info(
                "agent_cache_cleared agent_id=%s keys=%s", agent.id, deleted
            )
            return True
        except Exception as exc:
            logger.warning("agent_cache_clear_failed agent_id=%s err=%s", agent.id, exc)
            return False

    def _enqueue_cleanup(self, agent_id: UUID, company_id: UUID) -> None:
        try:
            from app.monitoring.queue import enqueue

            enqueue(
                {
                    "type": "agent.cleanup",
                    "agent_id": str(agent_id),
                    "company_id": str(company_id),
                }
            )
        except Exception as exc:
            # Soft delete already committed; cleanup can be retried by purge scan.
            logger.warning(
                "agent_cleanup_enqueue_failed agent_id=%s err=%s", agent_id, exc
            )
