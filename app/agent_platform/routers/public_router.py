"""Public Agent API — chat + widget for websites / apps / SaaS."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.agent_platform.dependencies import enforce_quota, verify_api_key, verify_api_key_from_value
from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.models.api_key import AgentApiKey
from app.agent_platform.models.quota import CompanyQuota
from app.agent_platform.gateway.service import AIGatewayService
from app.agent_platform.schemas import UnifiedChatRequest, UnifiedChatResponse
from app.agent_platform.publish.schemas import (
    PublicChatRequest,
    PublicChatResponse,
)
from app.agent_platform.publish.service import PublishService
from app.agent_platform.publish.chat_runtime import run_public_chat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public/v1", tags=["Public Agent API"])


def _resolve_key(request: Request, body: PublicChatRequest, db: Session) -> AgentApiKey:
    if body.api_key:
        key = verify_api_key_from_value(body.api_key, db)
    else:
        key = verify_api_key(request, db)

    from app.usage.dimensions import UsageDimension
    from app.usage.service import UsageService

    UsageService(db).check_quota(key.company_id, UsageDimension.AI_MESSAGES, quantity=1)
    UsageService(db).check_quota(key.company_id, UsageDimension.TOTAL_TOKENS, quantity=1)

    quota = db.query(CompanyQuota).filter(CompanyQuota.company_id == key.company_id).first()
    if quota:
        if quota.current_spend >= quota.monthly_spend_limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "quota_exceeded",
                    "dimension": "spend",
                    "current_usage": float(quota.current_spend),
                    "plan_limit": float(quota.monthly_spend_limit),
                    "upgrade_url": "/billing",
                },
            )
        if quota.current_tokens >= quota.monthly_token_limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "quota_exceeded",
                    "dimension": "total_tokens",
                    "current_usage": int(quota.current_tokens),
                    "plan_limit": int(quota.monthly_token_limit),
                    "upgrade_url": "/billing",
                },
            )
    return key


@router.get("/widget/embed", response_class=HTMLResponse, summary="Minimal embeddable chat UI")
def public_widget_embed(
    widget_id: str = "",
    embed_token: str = "",
    api_key: str = "",
    db: Session = Depends(get_db),
):
    """
    iframe shell. Credentials must be a short-lived signed embed token + widget_id.
    Live API keys in the query string are rejected (P0: no keys in URLs).
    """
    from fastapi import HTTPException, status as http_status
    from html import escape

    from app.agent_platform.publish.embed_tokens import (
        format_embed_credential,
        verify_embed_token,
    )

    if api_key and api_key.startswith("tht_live_"):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=(
                "Live API keys must not be passed in iframe URLs. "
                "Use widget_id + embed_token from the publish/embed endpoints."
            ),
        )

    if not widget_id or not embed_token:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="widget_id and embed_token are required",
        )

    claims = verify_embed_token(embed_token)
    if claims.get("wid") != widget_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="embed_token does not match widget_id",
        )

    # Ensure widget is published and load public config for theming.
    widget = PublishService(db).get_public_widget(widget_id)
    cfg = widget.get("config") or {}
    theme = escape(str(cfg.get("theme") or "light"))
    position = escape(str(cfg.get("position") or "bottom-right"))
    primary = escape(str(cfg.get("primary_color") or "#111827"))
    agent_name = escape(str(cfg.get("agent_name") or widget.get("agent_name") or "Assistant"))

    # Pass short-lived embed credential to widget.js (not a live tht_live_ key).
    embed_cred = escape(format_embed_credential(embed_token), quote=True)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>THTWAAT Chat</title>
<style>html,body{{margin:0;height:100%;background:transparent}}</style>
</head><body>
<script src="/widget.js" data-api-key="{embed_cred}" data-theme="{theme}" data-position="{position}" data-primary-color="{primary}" data-agent-name="{agent_name}" data-widget-id="{escape(widget_id)}"></script>
<script>
  // Auto-open for iframe preview
  window.addEventListener('load', function () {{
    setTimeout(function () {{ window.THTWAAT && window.THTWAAT.open && window.THTWAAT.open(); }}, 300);
  }});
</script>
</body></html>"""
    return HTMLResponse(html)


@router.get("/widget/{widget_id}", summary="Public widget config JSON")
def public_widget_config(widget_id: str, db: Session = Depends(get_db)):
    return PublishService(db).get_public_widget(widget_id)


@router.post(
    "/chat",
    response_model=PublicChatResponse,
    summary="Public chat for published agents (website / app / SaaS)",
)
async def public_chat(
    body: PublicChatRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    api_key = _resolve_key(request, body, db)
    reply, conversation_id, usage, extras = await run_public_chat(
        db, api_key, body.message, body.session_id, metadata=body.metadata
    )
    return PublicChatResponse(
        reply=reply,
        conversation_id=conversation_id,
        usage=usage,
        status=extras.get("status"),
        handoff=bool(extras.get("handoff")),
        lead=extras.get("lead"),
    )


@router.post(
    "/chat/stream",
    summary="SSE streaming public chat (thinking + progressive tokens)",
)
async def public_chat_stream(
    body: PublicChatRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    api_key = _resolve_key(request, body, db)

    async def event_gen() -> AsyncIterator[str]:
        try:
            from app.agent_platform.publish.chat_runtime import iter_public_chat_events

            async for kind, payload in iter_public_chat_events(
                db, api_key, body.message, body.session_id, metadata=body.metadata
            ):
                if kind == "thinking":
                    yield f"event: thinking\ndata: {json.dumps(payload)}\n\n"
                    await asyncio.sleep(0.01)
                elif kind == "token":
                    yield f"event: token\ndata: {json.dumps(payload)}\n\n"
                    await asyncio.sleep(0.012)
                elif kind == "done":
                    yield f"event: done\ndata: {json.dumps(payload)}\n\n"
                elif kind == "error":
                    yield f"event: error\ndata: {json.dumps(payload)}\n\n"
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
            yield f"event: error\ndata: {json.dumps({'message': detail})}\n\n"
        except Exception as exc:
            logger.error("stream chat failed: %s", exc, exc_info=True)
            yield f"event: error\ndata: {json.dumps({'message': 'Stream failed'})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post(
    "/chat/legacy",
    response_model=UnifiedChatResponse,
    summary="Legacy unified chat (Bearer + full message list)",
    include_in_schema=False,
)
async def public_chat_legacy(
    request: UnifiedChatRequest,
    api_key: AgentApiKey = Depends(enforce_quota),
    db: Session = Depends(get_db),
):
    if request.agent_id and str(api_key.agent_id) != str(request.agent_id):
        raise HTTPException(status_code=403, detail="API key is not authorized for this agent")

    agent = db.query(AgentConfig).filter(AgentConfig.id == api_key.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status != "PUBLISHED":
        raise HTTPException(status_code=403, detail="Agent is not published")

    request.company_id = str(api_key.company_id)
    if agent.system_prompt_template:
        request.messages.insert(0, {"role": "system", "content": agent.system_prompt_template})

    return await AIGatewayService.process_request(request)
