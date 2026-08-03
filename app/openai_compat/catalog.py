"""Build OpenAI-shaped model metadata for /v1/models (cached on Day 2)."""
from __future__ import annotations

import time
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.config.settings import settings


def _entry(model_id: str, owned_by: str, *, created: int | None = None) -> Dict[str, Any]:
    return {
        "id": model_id,
        "object": "model",
        "created": created if created is not None else int(time.time()),
        "owned_by": owned_by,
    }


def static_catalog() -> List[Dict[str, Any]]:
    """Baseline catalog — always available (stub + common gateway ids)."""
    created = 1_720_000_000
    rows = [
        _entry("thtwaat-stub-mini", "thtwaat", created=created),
        _entry("thtwaat-stub-fast", "thtwaat", created=created),
        _entry("gpt-4o-mini", "openai", created=created),
        _entry("gpt-4o", "openai", created=created),
        _entry("gemini-1.5-flash", "google", created=created),
        _entry("claude-3-5-sonnet", "anthropic", created=created),
    ]
    mode = (settings.OPENAI_COMPAT_INFERENCE or "stub").strip().lower()
    if mode == "stub":
        # Prefer stub ids first in list order for DX
        return rows
    return rows


def company_db_models(db: Session, company_id: UUID) -> List[Dict[str, Any]]:
    """Optional tenant-owned rows from ai_models (best-effort)."""
    try:
        from app.features.ai_platform.database.models import AiModel

        rows = (
            db.query(AiModel)
            .filter(AiModel.company_id == company_id)
            .order_by(AiModel.name.asc())
            .limit(200)
            .all()
        )
        out: List[Dict[str, Any]] = []
        for m in rows:
            created = int(m.created_at.timestamp()) if getattr(m, "created_at", None) else int(time.time())
            out.append(_entry(m.name, "organization", created=created))
        return out
    except Exception:
        return []


def build_models_payload(db: Session, company_id: UUID) -> Dict[str, Any]:
    seen: dict[str, Dict[str, Any]] = {}
    for item in [*static_catalog(), *company_db_models(db, company_id)]:
        seen[item["id"]] = item
    data = list(seen.values())
    data.sort(key=lambda x: x["id"])
    return {"object": "list", "data": data}


def find_model_in_payload(payload: Dict[str, Any], model_id: str) -> Dict[str, Any] | None:
    for item in payload.get("data") or []:
        if item.get("id") == model_id:
            return item
    return None
