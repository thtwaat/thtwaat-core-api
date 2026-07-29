"""Publish Service — publish agents, manage keys, embed/widget generation."""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.models.api_key import AgentApiKey
from app.agent_platform.publish.repository import PublishRepository
from app.agent_platform.publish.schemas import (
    AgentApiKeyCreatedResponse,
    AgentApiKeyListItem,
    AgentApiKeyRotateResponse,
    PublishResponse,
    UnpublishResponse,
    WidgetConfig,
    WidgetConfigResponse,
    WidgetConfigUpdate,
)
from app.config.settings import settings

logger = logging.getLogger(__name__)

KEY_PREFIX = "tht_live_"
DEFAULT_WIDGET = WidgetConfig()


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_raw_api_key() -> str:
    return f"{KEY_PREFIX}{secrets.token_urlsafe(24)}"


def generate_widget_id() -> str:
    return f"wgt_{secrets.token_hex(12)}"


def _audit(event: str, **fields) -> None:
    logger.info("audit_event=%s %s", event, " ".join(f"{k}={v}" for k, v in fields.items()))


class PublishService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PublishRepository(db)

    # ── Embed helpers ─────────────────────────────────────────────────────────

    def _base_url(self) -> str:
        return settings.PUBLIC_API_BASE_URL.rstrip("/")

    def build_public_chat_url(self) -> str:
        return f"{self._base_url()}/public/v1/chat"

    def build_iframe_url(self, widget_id: str) -> str:
        return f"{self._base_url()}/public/v1/widget/{widget_id}"

    def build_embed_script(
        self,
        api_key_or_placeholder: str,
        config: Optional[WidgetConfig] = None,
    ) -> str:
        cfg = config or DEFAULT_WIDGET
        prompts = "|".join(cfg.suggested_prompts or [])
        attrs = [
            f'src="{self._base_url()}/widget.js"',
            f'data-api-key="{api_key_or_placeholder}"',
            f'data-theme="{cfg.theme}"',
            f'data-position="{cfg.position}"',
            f'data-primary-color="{cfg.primary_color}"',
        ]
        if cfg.welcome_message:
            attrs.append(f'data-welcome="{cfg.welcome_message}"')
        if cfg.agent_name:
            attrs.append(f'data-agent-name="{cfg.agent_name}"')
        if prompts:
            attrs.append(f'data-prompts="{prompts}"')
        return "<script\n  " + "\n  ".join(attrs) + ">\n</script>"

    def build_iframe_tag(self, widget_id: str) -> str:
        url = self.build_iframe_url(widget_id)
        return (
            f'<iframe src="{url}" title="THTWAAT Chat" '
            f'width="380" height="600" style="border:0;border-radius:16px;" '
            f'allow="clipboard-write"></iframe>'
        )

    def get_embed_snippets(
        self,
        agent_id: UUID,
        company_id: UUID,
        api_key_placeholder: str = "tht_live_<YOUR_KEY>",
    ) -> "EmbedSnippetResponse":
        from app.agent_platform.publish.schemas import EmbedSnippetResponse

        agent = self.repo.get_agent_for_company(agent_id, company_id)
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        if not agent.widget_id:
            agent.widget_id = generate_widget_id()
            self.repo.save_agent(agent)

        config = self.widget_config_from_agent(agent)
        if not config.agent_name:
            config.agent_name = agent.name

        return EmbedSnippetResponse(
            agent_id=agent.id,
            widget_id=agent.widget_id,
            status=agent.status,
            script=self.build_embed_script(api_key_placeholder, config),
            iframe=self.build_iframe_tag(agent.widget_id),
            preview_url=f"{self._base_url()}/public/v1/widget/embed",
            config=config,
        )

    def widget_config_from_agent(self, agent: AgentConfig) -> WidgetConfig:
        raw = (agent.web_config or {}).get("widget") or {}
        merged = {**DEFAULT_WIDGET.model_dump(), **raw}
        # Cascade published company white-label defaults under agent overrides
        try:
            from app.branding.service import BrandingService

            company_widget = BrandingService(self.db).widget_defaults_for_company(agent.company_id)
            if company_widget:
                cascade = {
                    "theme": company_widget.get("chat_theme"),
                    "primary_color": company_widget.get("primary_color")
                    or company_widget.get("bubble_color"),
                    "logo": company_widget.get("header_logo_url"),
                    "avatar": company_widget.get("launcher_icon_url"),
                    "font_family": company_widget.get("font_family"),
                    "suggested_prompts": company_widget.get("suggested_prompts"),
                }
                for key, value in cascade.items():
                    if value and key not in raw:
                        merged[key] = value
        except Exception:
            pass
        return WidgetConfig(**merged)

    # ── Publish / Unpublish ───────────────────────────────────────────────────

    def publish(self, agent_id: UUID, company_id: UUID, user_id: UUID) -> PublishResponse:
        agent = self.repo.get_agent_for_company(agent_id, company_id)
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        raw_key: Optional[str] = None
        active_key = self.repo.get_active_key_for_agent(agent_id, company_id)

        if not active_key:
            raw_key, active_key = self._create_key_record(
                agent_id=agent_id,
                company_id=company_id,
                name="Publish Key",
            )

        if not agent.widget_id:
            agent.widget_id = generate_widget_id()

        web_config = dict(agent.web_config or {})
        if "widget" not in web_config:
            web_config["widget"] = DEFAULT_WIDGET.model_dump()
        agent.web_config = web_config

        agent.status = "PUBLISHED"
        agent.published_at = datetime.now(timezone.utc)
        agent.version = (agent.version or 0) + 1
        self.repo.save_agent(agent)

        widget_cfg = self.widget_config_from_agent(agent)
        if not widget_cfg.agent_name:
            widget_cfg.agent_name = agent.name

        embed_key = raw_key or f"{KEY_PREFIX}<YOUR_KEY>"

        _audit(
            "agent_published",
            agent_id=agent_id,
            company_id=company_id,
            user_id=user_id,
            widget_id=agent.widget_id,
        )

        return PublishResponse(
            status="PUBLISHED",
            agent_id=agent.id,
            api_key=raw_key,
            widget_id=agent.widget_id,
            public_chat_url=self.build_public_chat_url(),
            embed_script=self.build_embed_script(embed_key, widget_cfg),
            iframe_url=self.build_iframe_url(agent.widget_id),
            published_at=agent.published_at,
        )

    def unpublish(self, agent_id: UUID, company_id: UUID, user_id: UUID) -> UnpublishResponse:
        agent = self.repo.get_agent_for_company(agent_id, company_id)
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        agent.status = "DRAFT"
        self.repo.save_agent(agent)

        _audit(
            "agent_unpublished",
            agent_id=agent_id,
            company_id=company_id,
            user_id=user_id,
        )
        return UnpublishResponse(status="DRAFT", agent_id=agent.id)

    # ── API Keys ──────────────────────────────────────────────────────────────

    def _create_key_record(
        self,
        agent_id: UUID,
        company_id: UUID,
        name: str,
        expires_at: Optional[datetime] = None,
    ) -> Tuple[str, AgentApiKey]:
        raw_key = generate_raw_api_key()
        record = AgentApiKey(
            company_id=company_id,
            agent_id=agent_id,
            name=name,
            key_hash=hash_api_key(raw_key),
            key_prefix=raw_key[:16],
            expires_at=expires_at,
            is_active=True,
        )
        record = self.repo.create_key(record)
        _audit("agent_api_key_created", agent_id=agent_id, company_id=company_id, key_id=record.id)
        return raw_key, record

    def create_api_key(
        self,
        agent_id: UUID,
        company_id: UUID,
        name: str = "Default Key",
        expires_at: Optional[datetime] = None,
    ) -> AgentApiKeyCreatedResponse:
        agent = self.repo.get_agent_for_company(agent_id, company_id)
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        active_count = len(self.repo.list_keys(agent_id, company_id))
        try:
            from app.usage.dimensions import UsageDimension
            from app.usage.service import UsageService

            UsageService(self.db).check_quota(
                company_id,
                UsageDimension.API_KEYS,
                quantity=active_count + 1,
            )
        except HTTPException:
            raise
        except Exception:
            pass

        raw_key, record = self._create_key_record(agent_id, company_id, name, expires_at)
        try:
            from app.usage.dimensions import UsageDimension
            from app.usage.service import UsageService

            UsageService(self.db).record(
                company_id,
                UsageDimension.API_KEYS,
                active_count + 1,
                agent_id=agent_id,
                api_key_id=record.id,
                source="publish",
            )
        except Exception:
            pass
        return AgentApiKeyCreatedResponse(
            id=record.id,
            name=record.name,
            key_prefix=record.key_prefix,
            api_key=raw_key,
            expires_at=record.expires_at,
        )

    def list_api_keys(self, agent_id: UUID, company_id: UUID) -> List[AgentApiKeyListItem]:
        agent = self.repo.get_agent_for_company(agent_id, company_id)
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        return [AgentApiKeyListItem.model_validate(k) for k in self.repo.list_keys(agent_id, company_id)]

    def rotate_api_key(
        self,
        agent_id: UUID,
        company_id: UUID,
        key_id: UUID,
        name: Optional[str] = None,
    ) -> AgentApiKeyRotateResponse:
        old = self.repo.get_key(key_id, agent_id, company_id)
        if not old:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

        self.repo.revoke_key(old)
        raw_key, new_key = self._create_key_record(
            agent_id=agent_id,
            company_id=company_id,
            name=name or old.name or "Rotated Key",
            expires_at=old.expires_at,
        )
        _audit("agent_api_key_rotated", agent_id=agent_id, company_id=company_id, old_key_id=key_id, new_key_id=new_key.id)
        return AgentApiKeyRotateResponse(
            id=new_key.id,
            name=new_key.name,
            key_prefix=new_key.key_prefix,
            api_key=raw_key,
        )

    def disable_api_key(self, agent_id: UUID, company_id: UUID, key_id: UUID) -> AgentApiKeyListItem:
        key = self.repo.get_key(key_id, agent_id, company_id)
        if not key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        key = self.repo.revoke_key(key)
        _audit("agent_api_key_disabled", agent_id=agent_id, company_id=company_id, key_id=key_id)
        return AgentApiKeyListItem.model_validate(key)

    def delete_api_key(self, agent_id: UUID, company_id: UUID, key_id: UUID) -> None:
        key = self.repo.get_key(key_id, agent_id, company_id)
        if not key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        self.repo.delete_key(key)
        _audit("agent_api_key_deleted", agent_id=agent_id, company_id=company_id, key_id=key_id)

    # ── Widget ────────────────────────────────────────────────────────────────

    def get_widget_config(self, agent_id: UUID, company_id: UUID) -> WidgetConfigResponse:
        agent = self.repo.get_agent_for_company(agent_id, company_id)
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        if not agent.widget_id:
            agent.widget_id = generate_widget_id()
            self.repo.save_agent(agent)

        config = self.widget_config_from_agent(agent)
        if not config.agent_name:
            config.agent_name = agent.name
        return WidgetConfigResponse(
            agent_id=agent.id,
            widget_id=agent.widget_id,
            status=agent.status,
            config=config,
            public_chat_url=self.build_public_chat_url(),
            embed_script=self.build_embed_script(f"{KEY_PREFIX}<YOUR_KEY>", config),
            iframe_url=self.build_iframe_url(agent.widget_id),
        )

    def update_widget_config(
        self,
        agent_id: UUID,
        company_id: UUID,
        update: WidgetConfigUpdate,
    ) -> WidgetConfigResponse:
        agent = self.repo.get_agent_for_company(agent_id, company_id)
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        if not agent.widget_id:
            agent.widget_id = generate_widget_id()

        current = self.widget_config_from_agent(agent).model_dump()
        patch = update.model_dump(exclude_unset=True)
        current.update(patch)

        web_config = dict(agent.web_config or {})
        web_config["widget"] = current
        agent.web_config = web_config
        self.repo.save_agent(agent)

        return self.get_widget_config(agent_id, company_id)

    def get_public_widget(self, widget_id: str) -> dict:
        agent = self.repo.get_agent_by_widget_id(widget_id)
        if not agent or agent.status != "PUBLISHED":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")
        config = self.widget_config_from_agent(agent)
        return {
            "widget_id": agent.widget_id,
            "agent_name": agent.name,
            "status": agent.status,
            "config": config.model_dump(),
            "public_chat_url": self.build_public_chat_url(),
        }
