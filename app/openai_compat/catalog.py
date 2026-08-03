"""Build OpenAI-shaped model metadata for /v1/models."""
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


def stub_catalog() -> List[Dict[str, Any]]:
    """CI / local stub ids — only when OPENAI_COMPAT_INFERENCE=stub."""
    created = 1_720_000_000
    return [
        _entry("thtwaat-stub-mini", "thtwaat", created=created),
        _entry("thtwaat-stub-fast", "thtwaat", created=created),
    ]


def static_catalog() -> List[Dict[str, Any]]:
    """Deprecated alias — prefer registry-backed build_models_payload."""
    return stub_catalog()


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


def registry_catalog() -> List[Dict[str, Any]]:
    """Models from enabled Sem03 inference providers only."""
    from app.openai_compat.providers import ensure_providers_registered

    registry = ensure_providers_registered()
    out: List[Dict[str, Any]] = []
    for item in registry.all_enabled_models():
        public = {k: v for k, v in item.items() if not str(k).startswith("_")}
        out.append(public)
    return out


def build_models_payload(db: Session, company_id: UUID) -> Dict[str, Any]:
    seen: dict[str, Dict[str, Any]] = {}
    mode = (settings.OPENAI_COMPAT_INFERENCE or "stub").strip().lower()
    rows: List[Dict[str, Any]] = []
    if mode == "stub":
        rows.extend(stub_catalog())
    rows.extend(registry_catalog())
    rows.extend(company_db_models(db, company_id))
    for item in rows:
        seen[item["id"]] = item
    data = list(seen.values())
    data.sort(key=lambda x: x["id"])
    return {"object": "list", "data": data}


def find_model_in_payload(payload: Dict[str, Any], model_id: str) -> Dict[str, Any] | None:
    for item in payload.get("data") or []:
        if item.get("id") == model_id:
            return item
    return None
