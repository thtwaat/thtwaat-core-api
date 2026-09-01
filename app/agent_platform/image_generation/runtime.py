"""Image-generation turn orchestration — the image equivalent of
``app/agent_platform/voice/voice_runtime.py``.

Prompt in -> ImageGenerationProvider.generate() -> generated image bytes ->
best-effort durable storage (StorageService) + base64 in the response.
Conversation/Message persistence, capability gating and quota all reuse the
same helpers/services text chat and voice use.

Consistent with the voice module's precedent (audio bytes are never
persisted into a ``Message`` row, only the text transcript/reply are):
generated image BYTES are not persisted into ``Message`` either — only a
short text note. The bytes themselves ARE durably persisted via
``StorageService`` (unlike voice audio, which isn't stored anywhere), so a
future enhancement can link them back into conversation history without
regenerating anything; that link just doesn't exist yet (no new column).
"""
from __future__ import annotations

import base64
import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from starlette.datastructures import Headers, UploadFile

from app.agent_platform.agent_runtime import (
    AgentRuntime,
    agent_capabilities,
    resolve_image_generation_config,
)
from app.agent_platform.image_generation.credentials import resolve_image_generation_api_key
from app.agent_platform.image_generation.registries import ImageGenerationProviderRegistry
from app.agent_platform.models.conversation import Conversation, Message
from app.usage.dimensions import UsageDimension
from app.usage.service import UsageService

logger = logging.getLogger(__name__)


def _get_or_create_conversation(
    db: Session,
    *,
    company_id: Any,
    agent: Any,
    channel: str,
    session_id: Optional[str],
    title_hint: str,
) -> Conversation:
    conv: Optional[Conversation] = None
    if session_id:
        try:
            conv = (
                db.query(Conversation)
                .options(joinedload(Conversation.messages))
                .filter(
                    Conversation.id == UUID(session_id),
                    Conversation.company_id == company_id,
                    Conversation.agent_id == agent.id,
                )
                .first()
            )
        except ValueError:
            conv = None

    if conv:
        return conv

    conv = Conversation(
        company_id=company_id,
        agent_id=agent.id,
        title=title_hint[:80],
        channel=channel,
        status="open",
        extra_metadata={},
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


async def _persist_image(
    db: Session, *, company_id: Any, image_bytes: bytes, mime_type: str
) -> Optional[str]:
    """Best-effort durable copy via the existing StorageService. Returns a
    (dashboard-authenticated) download URL, or None if storage failed —
    never blocks the response, since data_base64 always carries the image."""
    try:
        from app.storage.service import StorageService

        ext = "png" if mime_type == "image/png" else mime_type.split("/")[-1]
        upload = UploadFile(
            file=io.BytesIO(image_bytes),
            size=len(image_bytes),
            filename=f"generated.{ext}",
            headers=Headers({"content-type": mime_type}),
        )
        service = StorageService(db)
        stored = await service.upload_file(upload, company_id=company_id, user_id=None)
        return service.get_download_url(stored.id)
    except Exception as exc:
        logger.warning("Image generation: durable storage upload failed: %s", exc)
        return None


class ImageGenerationRuntime:
    """Shared execution core for a single image-generation turn."""

    @staticmethod
    async def run_image_generation_turn(
        db: Session,
        *,
        agent: Any,
        company_id: Any,
        channel: str,
        prompt: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        usage_ctx: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        prompt = (prompt or "").strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="An image prompt is required.")

        caps = agent_capabilities(getattr(agent, "web_config", None))
        img_cfg = resolve_image_generation_config(agent)
        AgentRuntime.check_image_generation_request(caps, img_cfg["provider"], img_cfg["model"])

        usage_svc = UsageService(db)
        usage_svc.check_quota(company_id, UsageDimension.AI_MESSAGES, quantity=1)

        api_key = resolve_image_generation_api_key(img_cfg["provider"])
        if not api_key:
            raise HTTPException(
                status_code=503,
                detail=f"Image generation provider '{img_cfg['provider']}' is not configured.",
            )

        provider = ImageGenerationProviderRegistry.get_provider(img_cfg["provider"], api_key)
        try:
            results = await provider.generate(
                prompt,
                model=img_cfg["model"],
                size=img_cfg["size"],
                quality=img_cfg["quality"],
                n=1,
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Image generation failed for agent_id=%s: %s", agent.id, exc, exc_info=True)
            raise HTTPException(
                status_code=502, detail="Image generation failed. Please try again."
            ) from exc

        if not results:
            raise HTTPException(status_code=502, detail="Image provider returned no images.")

        conv = _get_or_create_conversation(
            db,
            company_id=company_id,
            agent=agent,
            channel=channel,
            session_id=session_id,
            title_hint=prompt,
        )
        if metadata:
            existing = dict(conv.extra_metadata or {})
            existing.update(metadata)
            conv.extra_metadata = existing
            db.add(conv)
            db.commit()

        db.add(Message(conversation_id=conv.id, role="user", content=prompt))
        note = f"Generated {len(results)} image(s) for: {results[0].revised_prompt or prompt}"
        db.add(Message(conversation_id=conv.id, role="assistant", content=note))
        conv.updated_at = datetime.now(timezone.utc)
        db.commit()

        images: List[Dict[str, Any]] = []
        for result in results:
            url = await _persist_image(
                db, company_id=company_id, image_bytes=result.image_bytes, mime_type=result.mime_type
            )
            images.append(
                {
                    "data_base64": base64.b64encode(result.image_bytes).decode("ascii"),
                    "mime_type": result.mime_type,
                    "url": url,
                    "provider": result.provider,
                    "model": result.model,
                    "revised_prompt": result.revised_prompt,
                }
            )

        usage_svc.record(
            company_id,
            UsageDimension.IMAGES_GENERATED,
            len(results),
            agent_id=agent.id,
            source=(usage_ctx or {}).get("source", "image_generation"),
            emit_webhook=False,
        )
        usage_svc.record(
            company_id,
            UsageDimension.AI_MESSAGES,
            1,
            agent_id=agent.id,
            source=(usage_ctx or {}).get("source", "image_generation"),
            emit_webhook=False,
        )

        return {
            "conversation_id": str(conv.id),
            "images": images,
            "usage": {
                "provider": img_cfg["provider"],
                "model": img_cfg["model"],
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost": 0.0,
            },
            "status": conv.status,
        }
